"""Keep the live replay sessions, and reap the abandoned ones.

One job: map session id -> ReplaySession, and make sure a closed browser tab
does not leave a playing session stepping forever behind it.

A session outlives its subscribers briefly on purpose: a page refresh drops the
SSE connection and reopens it a moment later, and killing the session in that
gap would lose the cursor and the warmed-up indicator state.
"""

from __future__ import annotations

import logging
import threading
import time

from src.config import replay as cfg
from src.replay.session import ReplaySession

logger = logging.getLogger(__name__)

_SESSIONS: dict[str, ReplaySession] = {}
_LOCK = threading.RLock()
_REAPER: threading.Thread | None = None


def create(symbol: str, timeframe: str) -> ReplaySession:
    _ensure_reaper()
    session = ReplaySession(symbol, timeframe)
    with _LOCK:
        _SESSIONS[session.id] = session
    logger.info("Replay %s: created (%s %s)", session.id, symbol, timeframe)
    return session


def get(session_id: str) -> ReplaySession:
    with _LOCK:
        session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError(f"no replay session {session_id!r}")
    session.last_seen = time.monotonic()
    return session


def stop(session_id: str) -> None:
    with _LOCK:
        session = _SESSIONS.pop(session_id, None)
    if session:
        session.stop()
        logger.info("Replay %s: stopped", session_id)


def stop_all() -> None:
    with _LOCK:
        ids = list(_SESSIONS)
    for session_id in ids:
        stop(session_id)


def count() -> int:
    with _LOCK:
        return len(_SESSIONS)


def _ensure_reaper() -> None:
    global _REAPER
    if _REAPER is not None and _REAPER.is_alive():
        return
    _REAPER = threading.Thread(target=_reap, name="replay-reaper", daemon=True)
    _REAPER.start()


def _reap() -> None:
    while True:
        time.sleep(cfg.REAP_INTERVAL)
        now = time.monotonic()
        with _LOCK:
            dead = [
                sid for sid, s in _SESSIONS.items()
                if s.subscriber_count == 0 and now - s.last_seen > cfg.SESSION_IDLE_TIMEOUT
            ]
        for sid in dead:
            logger.info("Replay %s: idle - reaping", sid)
            stop(sid)
