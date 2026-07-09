"""The replay API: control in, snapshots out. Transport-free.

One job: map a parsed replay request to a response, and expose the snapshot
stream as an iterator of SSE frames. It never touches a socket - server.py owns
HTTP - so every route here is testable without binding a port.

Control is POST; the stream is a GET that stays open:

  POST /api/replay/start  {symbol, timeframe, index, history}  -> seed info
  POST /api/replay/step   {session, n}                         -> {cursor}
  POST /api/replay/play   {session, speed}                     -> {playing}
  POST /api/replay/pause  {session}                            -> {playing}
  POST /api/replay/stop   {session}                            -> {}
  GET  /api/replay/sessions                                    -> live sessions
  GET  /api/replay/stream?session=ID                           -> text/event-stream

The stream is the point. The chart subscribes and draws each row; the TUI
subscribes and prints it. Both see the identical snapshot, because there is only
one cursor and one set of indicator state, and it lives here.
"""

from __future__ import annotations

import json
import logging
import queue

from src.config import replay as cfg
from src.replay import manager
from src.replay.snapshot import Snapshot

logger = logging.getLogger(__name__)

JSON = "application/json"
SSE = "text/event-stream"

Response = tuple[int, str, bytes, dict]


def _json(status: int, payload: dict) -> Response:
    return status, JSON, json.dumps(payload).encode(), {}


def _error(status: int, message: str) -> Response:
    return _json(status, {"error": message})


def handle_get(path: str, query: dict) -> Response:
    """Read-only replay routes. The stream is handled by the server directly."""
    if path == "/api/replay/sessions":
        return _json(200, {"sessions": manager.list_sessions()})
    return _error(404, f"no such route: {path}")


def handle_post(path: str, body: dict) -> Response:
    """Route one replay control request. Never raises."""
    try:
        if path == "/api/replay/start":
            return _start(body)
        if path == "/api/replay/step":
            return _step(body)
        if path == "/api/replay/play":
            return _play(body)
        if path == "/api/replay/pause":
            return _pause(body)
        if path == "/api/replay/stop":
            manager.stop(str(body.get("session", "")))
            return _json(200, {})
    except KeyError as exc:
        return _error(404, str(exc))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:
        logger.exception("Unhandled error on %s", path)
        return _error(500, "internal error - see server log")
    return _error(404, f"no such route: {path}")


def _start(body: dict) -> Response:
    symbol = str(body.get("symbol", "")).upper()
    timeframe = str(body.get("timeframe", "")).lower()
    if not symbol or not timeframe:
        raise ValueError("both 'symbol' and 'timeframe' are required")
    if "index" not in body:
        raise ValueError("'index' is required")

    # One replay at a time per client. `replace` handles the id the caller still
    # remembers; `owner` handles the ones it has forgotten - after a page
    # refresh, or after --reload restarted the server underneath it. Without the
    # second, orphaned sessions accumulate until the idle reaper notices, and a
    # table attaching later cannot tell which replay is "the" replay.
    previous = body.get("replace")
    if previous:
        manager.stop(str(previous))

    owner = str(body.get("owner", ""))
    manager.stop_owned_by(owner)

    # The profile indicator's state IS the range it has accumulated, so switching
    # which range it draws means a new session, seeded from scratch. The chart
    # re-seeds at the same bar, which it already knows how to do.
    session = manager.create(symbol, timeframe, owner, body.get("profile"))
    return _json(200, session.seed(int(body["index"]), body.get("history")))


def _step(body: dict) -> Response:
    session = manager.get(str(body.get("session", "")))
    session.pause()
    for _ in range(max(1, int(body.get("n", 1)))):
        if session.step() is None:
            break
    return _json(200, {"cursor": session.cursor, "at_end": session.at_end})


def _play(body: dict) -> Response:
    session = manager.get(str(body.get("session", "")))
    if "speed" in body:
        session.set_speed(int(body["speed"]))
    session.play()
    return _json(200, {"playing": session.playing, "speed": session.speed})


def _pause(body: dict) -> Response:
    session = manager.get(str(body.get("session", "")))
    session.pause()
    return _json(200, {"playing": False, "speed": session.speed})


def stream(session_id: str):
    """Yield SSE frames for a session until it stops or the client disconnects.

    A keepalive comment goes out when nothing has happened, because a silent
    stream gets closed by browsers and proxies and the reconnect would lose the
    cursor's place in the user's eye, if not in ours.
    """
    try:
        session = manager.get(session_id)
    except KeyError:
        return          # retired between the server's check and here
    q = session.subscribe()
    try:
        yield _frame(session_id,
                     {"state": {"playing": session.playing, "speed": session.speed,
                                "at_end": session.at_end, "cursor": session.cursor}})
        while True:
            try:
                item = q.get(timeout=cfg.SSE_KEEPALIVE_SECONDS)
            except queue.Empty:
                yield b": keepalive\n\n"
                continue
            if item is None:      # sentinel from session.stop()
                break
            payload = item.to_dict() if isinstance(item, Snapshot) else item
            yield _frame(session_id, payload)
    finally:
        session.unsubscribe(q)


def _frame(session_id: str, payload: dict) -> bytes:
    """Every frame names its session, so a client can reject a stranger's.

    A retired session's last snapshots can still be in flight when the chart has
    already cut back and seeded a new one. Drawn, they hand the chart a bar older
    than its newest - and, worse, a bar the current cursor has not revealed.
    Unlabelled, the client cannot tell whose row it is holding.
    """
    return f"data: {json.dumps({**payload, 'session': session_id})}\n\n".encode()
