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

from src.config import table as cfg

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
    """Reads a session's SSE stream on a thread; hands rows to a queue.

    Survives two things that used to be fatal. A retired session closes the
    connection *cleanly*, which is indistinguishable from a healthy close - so
    every reconnect waits, and the delay grows. And when the session it was
    watching is gone, it looks for the one that replaced it: switching timeframe
    on the chart retires a session and starts another, and the table follows.

    Session changes reach the window as a ``{"session_changed": info}`` payload
    on the same queue, so the window learns about it the same way it learns
    about everything else.
    """

    def __init__(self, base_url: str, session_id: str, rung: str | None = None) -> None:
        self.base_url = base_url
        self.session_id = session_id
        # Which scale this table reads. The session publishes a row per rung on
        # one stream; a table takes one of them and ignores the rest. Three
        # tables on three rungs therefore cannot drift apart - they are three
        # filters over one cursor, not three replays.
        self.rung = rung
        self.queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._delay = cfg.RECONNECT_DELAY_S

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="table-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._read(f"{self.base_url}/api/replay/stream?session={self.session_id}")
            except urllib.error.HTTPError as exc:
                if exc.code != 404:        # 404 = the session is gone; expected
                    logger.warning("Stream error %s", exc)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                if self._stop.is_set():
                    return
                logger.debug("Stream dropped (%s)", exc)

            if self._stop.is_set():
                return
            # A retired session closes the connection CLEANLY, which from here
            # is indistinguishable from a healthy close. So check whether it is
            # still there, and never retry without waiting - retrying a dead
            # session with no delay is how a reconnect storm starts.
            if not self._alive() and self._adopt():
                continue    # a fresh session is waiting: attach now, not in 500ms
            self._backoff()
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
                    frame = json.loads(line[6:])
                except ValueError:
                    logger.debug("Skipping unparseable frame")
                    continue
                # Transport state and session changes belong to every subscriber;
                # only a snapshot carries a rung, and only ours is ours.
                if self.rung and frame.get("rung") and frame["rung"] != self.rung:
                    continue
                self.queue.put(frame)
                self._delay = cfg.RECONNECT_DELAY_S   # data flowed: reset backoff

    def _backoff(self) -> None:
        self._stop.wait(self._delay)
        self._delay = min(self._delay * 2, cfg.RECONNECT_DELAY_MAX_S)

    def _alive(self) -> bool:
        try:
            return any(s["id"] == self.session_id for s in list_sessions(self.base_url))
        except OSError:
            return True    # the server is unreachable, not the session retired

    def _adopt(self) -> bool:
        """Our session is gone. Attach to whatever replaced it, if anything.

        Switching timeframe on the chart retires one session and starts another.
        Following it is what the user means by "watch the replay". Only adopt
        when exactly one is running: with several, we would be guessing.

        The new session need not publish the rung we were reading - a 30s replay
        has a 3m rung and a 15m one does not. Following it while filtering for a
        rung it will never send is a table that sits empty forever and says
        nothing about why. So the rung is reconciled here, and the window is told
        which scale it is actually looking at.
        """
        if not cfg.ADOPT_NEW_SESSION:
            return False
        try:
            running = list_sessions(self.base_url)
        except OSError:
            return False
        if len(running) != 1:
            return False

        session = running[0]
        logger.info("Session %s retired; following %s (%s %s)", self.session_id,
                    session["id"], session["symbol"], session["timeframe"])
        self.session_id = session["id"]
        self._delay = cfg.RECONNECT_DELAY_S
        self.queue.put({"session_changed": {**session, "timeframe": self._rung_of(session)}})
        return True

    def _rung_of(self, session: dict) -> str:
        """Keep our scale if the new session has it; otherwise read its base."""
        rungs = session.get("rungs") or [session["timeframe"]]
        if not self.rung or self.rung in rungs:
            return self.rung or session["timeframe"]

        logger.warning("%s publishes no %s rung (only %s); reading %s instead",
                       session["timeframe"], self.rung, ", ".join(rungs),
                       session["timeframe"])
        self.rung = session["timeframe"]
        return self.rung


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
    if running and not symbol:
        # Several can be running if a browser was refreshed before ownership
        # retired its orphan. The newest is the one the user just started, and
        # guessing that is far better than refusing to open. --session overrides.
        newest = max(running, key=lambda s: s.get("started", 0))
        if len(running) > 1:
            logger.info("%d replays running; attaching to the newest (%s %s)",
                        len(running), newest["symbol"], newest["timeframe"])
        return newest

    if not symbol:
        raise NoSession(
            "no replay is running. Hit Replay on the chart and click a bar, "
            "or start one here with --symbol NQT --timeframe 5m")

    timeframe = timeframe or "5m"
    index = at_index if at_index is not None else bar_count(base_url, symbol, timeframe) // 2
    seed = start_session(base_url, symbol, timeframe, index)
    return {**seed, "id": seed["session"]}
