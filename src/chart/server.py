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

from src.chart import api, lifecycle, packer
from src.config import chart as chart_cfg

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
        if parsed.path.startswith("/api/"):
            self._serve_api(parsed.path, parse_qs(parsed.query))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _serve_api(self, path: str, query: dict) -> None:
        status, content_type, body, extra = api.handle(path, query)
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
          pack_first: bool = True, on_ready=None) -> None:
    """Reclaim the port, pack any missing bar caches, then serve until stopped.

    ``on_ready`` fires once the socket is bound and accepting - the only safe
    moment to open a browser, since the first run may spend seconds packing.

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
    atexit.register(lifecycle.clear_pidfile)

    stop = threading.Event()
    # shutdown() blocks until serve_forever() returns, so it must never be
    # called from the thread running serve_forever - hence serving off-thread
    # while the main thread waits for the stop signal.
    lifecycle.install_signal_handlers(stop.set)

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


def _shutdown(httpd: ChartServer, host: str, port: int) -> None:
    """Stop serving, release the socket, and confirm the port is actually free."""
    httpd.shutdown()
    httpd.server_close()
    lifecycle.clear_pidfile()

    if lifecycle.wait_until_free(host, port, chart_cfg.SHUTDOWN_TIMEOUT):
        logger.info("Chart server stopped - port %d confirmed closed", port)
    else:
        logger.error("Chart server stopped but port %d is STILL in use", port)
