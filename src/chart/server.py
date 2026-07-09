"""Serve the chart: static frontend files plus the /api routes.

One job: speak HTTP. It parses a request, hands /api paths to api.py, serves
everything else as a static file out of the frontend directory, and writes the
bytes back. No data logic lives here - that is store.py and api.py; owning the
port is lifecycle.py.

Threading, because a browser opens several connections at once and a blocking
single-threaded server would serialize the module fetches behind them.
"""

from __future__ import annotations

import atexit
import json
import logging
import mimetypes
import os
import socket
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.chart import api, autoreload, lifecycle, packer
from src.config import chart as chart_cfg
from src.replay import manager as replay_manager
from src.replay import routes as replay_routes

logger = logging.getLogger(__name__)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class ChartServer(ThreadingHTTPServer):
    """A server that refuses to share its port."""

    # Handler threads must not outlive the process, or Ctrl-C leaves a zombie
    # holding the socket while a keep-alive connection idles.
    daemon_threads = True

    # HTTPServer defaults this to True. On Windows that is not "reuse a
    # TIME_WAIT port", it is "let another process bind a port I am actively
    # listening on" - which is precisely how duplicate servers stack up.
    allow_reuse_address = sys.platform != "win32"

    def server_bind(self) -> None:
        if sys.platform == "win32":
            # Make the exclusion explicit rather than relying on the default.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ChartHandler(SimpleHTTPRequestHandler):
    """Static files from FRONTEND_DIR; /api/* delegated to api.handle()."""

    # HTTP/1.1 keeps the connection alive. Replay issues a prefetch every few
    # hundred bars, and on 1.0 each one would pay a fresh TCP handshake. Safe
    # because every response we write sends an accurate Content-Length.
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, root: Path, **kwargs):
        super().__init__(*args, directory=str(root), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib's casing
        parsed = urlparse(self.path)
        if parsed.path == "/api/replay/stream":
            self._serve_stream(parse_qs(parsed.query))
            return
        if parsed.path.startswith("/api/"):
            self._serve_api(parsed.path, parse_qs(parsed.query))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/replay/"):
            self.send_error(404, "no such route")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            status, content_type, payload, extra = 400, "application/json", b'{"error":"bad JSON"}', {}
        else:
            status, content_type, payload, extra = replay_routes.handle_post(parsed.path, body)
        self._write(status, content_type, payload, extra)

    def _serve_stream(self, query: dict) -> None:
        """Hold the connection open and push snapshots as they are published.

        No Content-Length is possible for an open-ended stream, so the response
        is delimited by closing the connection. That is why HTTP/1.1 keep-alive
        is switched off for this one request and only this one.
        """
        session_id = (query.get("session", [""])[0] or "")
        try:
            frames = replay_routes.stream(session_id)
        except KeyError as exc:
            self._write(404, "application/json", json.dumps({"error": str(exc)}).encode(), {})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()

        try:
            for frame in frames:
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The tab closed. Normal; the generator's finally unsubscribes.
            logger.debug("Replay stream closed by client")
        finally:
            frames.close()

    def _serve_api(self, path: str, query: dict) -> None:
        self._write(*api.handle(path, query))

    def _write(self, status: int, content_type: str, body: bytes, extra: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in extra.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        # Lets a relaunch recognize this port as ours before reclaiming it.
        self.send_header(lifecycle.SIGNATURE_HEADER, lifecycle.SIGNATURE)
        # Static assets are read off disk each request; never let a browser
        # serve a stale chart module after an edit.
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        # Route stdlib's stderr access log into our logging config.
        logger.debug("%s - %s", self.address_string(), fmt % args)


def serve(host: str = chart_cfg.HOST, port: int = chart_cfg.PORT, *,
          pack_first: bool = True, on_ready=None, reload: bool = False) -> bool:
    """Reclaim the port, pack any missing bar caches, then serve until stopped.

    ``on_ready`` fires once the socket is bound and accepting - the only safe
    moment to open a browser, since the first run may spend seconds packing.

    With ``reload``, a change to any watched .py file stops the server the same
    way Ctrl-C does. Returns True if it stopped for a reload, so the caller can
    start it again. Static files never need this: they are read per request.

    Exits only after the port is confirmed free, so a relaunch never races a
    dying predecessor and servers cannot stack.
    """
    lifecycle.stop_running(host, port)

    if pack_first:
        metas = packer.pack_all()
        logger.info("Chart cache ready: %d datasets", len(metas))

    handler = partial(ChartHandler, root=chart_cfg.FRONTEND_DIR)
    httpd = ChartServer((host, port), handler)
    lifecycle.write_pidfile(host, port)
    atexit.register(lifecycle.clear_pidfile, port)

    stop = threading.Event()
    changed = threading.Event()
    # shutdown() blocks until serve_forever() returns, so it must never be
    # called from the thread running serve_forever - hence serving off-thread
    # while the main thread waits for the stop signal.
    lifecycle.install_signal_handlers(stop.set)
    if reload:
        autoreload.watch([Path(__file__).resolve().parents[1]], changed, stop)

    serving = threading.Thread(target=httpd.serve_forever, name="chart-http", daemon=True)
    serving.start()
    logger.info("Chart server: http://%s:%d  (pid %d)", host, port, os.getpid())

    if on_ready is not None:
        on_ready(f"http://{host}:{port}")

    try:
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown(httpd, host, port)
    return changed.is_set()


def _shutdown(httpd: ChartServer, host: str, port: int) -> None:
    """Stop serving, release the socket, and confirm the port is actually free."""
    # Playing sessions hold a stepping thread; stop them before the socket goes,
    # or a reload races a session still pushing into a dead connection.
    replay_manager.stop_all()
    httpd.shutdown()
    httpd.server_close()
    lifecycle.clear_pidfile(port)

    if lifecycle.wait_until_free(host, port, chart_cfg.SHUTDOWN_TIMEOUT):
        logger.info("Chart server stopped - port %d confirmed closed", port)
    else:
        logger.error("Chart server stopped but port %d is STILL in use", port)
