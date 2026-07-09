"""Subscribe to a replay session's snapshot stream, from another process.

One job: talk HTTP to the chart server - find a session, optionally start one,
and read its SSE stream on a background thread, pushing each snapshot onto a
queue. It never touches Qt, so the window stays responsive and this stays
testable without one.

The table is a *second subscriber* to the session the chart is already driving.
It does not own the cursor, cannot step it, and cannot disagree with it: the
same Snapshot object is delivered to both. That is the whole reason the replay
session moved to the server.

Standard library only. No requests, no sse-client - an SSE frame is
``data: {...}\\n\\n`` and reading it needs nothing but a socket.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class NoSession(RuntimeError):
    """No replay is running. Start one on the chart, or pass --symbol."""


def _get(url: str, timeout: float = 5.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def _post(url: str, body: dict, timeout: float = 15.0) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def list_sessions(base_url: str) -> list[dict]:
    return _get(f"{base_url}/api/replay/sessions")["sessions"]


def start_session(base_url: str, symbol: str, timeframe: str, index: int) -> dict:
    return _post(f"{base_url}/api/replay/start",
                 {"symbol": symbol, "timeframe": timeframe, "index": index})


def locate(base_url: str, symbol: str, timeframe: str, epoch_seconds: int) -> dict:
    return _get(f"{base_url}/api/locate?symbol={symbol}&timeframe={timeframe}"
                f"&time={int(epoch_seconds)}")


def bar_count(base_url: str, symbol: str, timeframe: str) -> int:
    datasets = _get(f"{base_url}/api/datasets")
    return datasets[symbol][timeframe]["count"]


class SnapshotStream:
    """Reads one session's SSE stream on a thread; hands rows to a queue."""

    def __init__(self, base_url: str, session_id: str) -> None:
        self.base_url = base_url
        self.session_id = session_id
        self.queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="table-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        url = f"{self.base_url}/api/replay/stream?session={self.session_id}"
        while not self._stop.is_set():
            try:
                self._read(url)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                if self._stop.is_set():
                    return
                # The session outlives a dropped connection on purpose, so
                # reconnecting picks the cursor back up where it was.
                logger.warning("Stream dropped (%s); reconnecting", exc)
                self._stop.wait(1.0)
        logger.info("Stream stopped")

    def _read(self, url: str) -> None:
        with urllib.request.urlopen(url, timeout=None) as response:
            for raw in response:
                if self._stop.is_set():
                    return
                line = raw.decode("utf-8", "replace").rstrip("\n")
                if not line.startswith("data: "):
                    continue        # ": keepalive" comments, blank separators
                try:
                    self.queue.put(json.loads(line[6:]))
                except ValueError:
                    logger.debug("Skipping unparseable frame")


def resolve_session(base_url: str, session_id: str | None,
                    symbol: str | None, timeframe: str | None,
                    at_index: int | None) -> dict:
    """Attach to the running replay, or start one. Returns its session info.

    Preference order matters: an explicit id wins; otherwise attach to the
    single running session, because the point is to watch what the chart is
    already doing. Only start a new one when asked to.
    """
    if session_id:
        for session in list_sessions(base_url):
            if session["id"] == session_id:
                return session
        raise NoSession(f"no session {session_id!r} on {base_url}")

    running = list_sessions(base_url)
    if len(running) == 1 and not symbol:
        return running[0]
    if len(running) > 1 and not symbol:
        ids = ", ".join(s["id"] for s in running)
        raise NoSession(f"several replays are running ({ids}); pass --session <id>")

    if not symbol:
        raise NoSession(
            "no replay is running. Hit Replay on the chart and click a bar, "
            "or start one here with --symbol NQT --timeframe 5m")

    timeframe = timeframe or "5m"
    index = at_index if at_index is not None else bar_count(base_url, symbol, timeframe) // 2
    seed = start_session(base_url, symbol, timeframe, index)
    return {**seed, "id": seed["session"]}
