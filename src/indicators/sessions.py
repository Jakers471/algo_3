"""Which trading session a bar closed in, and how far into it we are.

One job: as each event arrives, say what session it belongs to (Asia / London /
NY), whether that session just changed, and the running extremes of the session
so far. Pure state machine - it holds only what it has already seen.

Sessions are defined in ``config/session.py`` (Eastern windows; the 17:00-18:00 ET
gap is the CME maintenance halt). Membership is ``start < minute <= end``, because
bars are CLOSE-stamped: a bar labelled T covers ``(T - step, T]`` and therefore
belongs to the session its interval closed in. Getting this wrong orphans the
17:00 ET bar - NY's last - into no session at all.

The running high/low are the session's extremes UP TO the current event, never
the session's final extremes. A replay cursor sitting mid-session sees exactly
what a trader standing there would have seen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.config import session as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

# UTC-hour -> offset seconds. Converting a timestamp to Eastern per event costs
# ~11us; over a replay buffer that dominated the whole indicator pass. US offsets
# are whole hours and DST flips on an hour boundary, so the offset is constant
# within any UTC hour and this cache is exact, not an approximation.
# (test_sessions.py checks it against tz_convert across both DST transitions.)
_OFFSET_CACHE: dict[int, int] = {}


def _minute_of_day(ts) -> int:
    """Eastern minute-of-day for a UTC timestamp, via cached integer offsets."""
    epoch = ts.value // 1_000_000_000 if hasattr(ts, "value") else int(ts.timestamp())
    hour = epoch // 3600
    offset = _OFFSET_CACHE.get(hour)
    if offset is None:
        local = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(ZoneInfo(cfg.SESSION_TZ))
        offset = int(local.utcoffset().total_seconds())
        _OFFSET_CACHE[hour] = offset
    return ((epoch + offset) // 60) % 1440


def session_for(minute_of_day: int) -> str | None:
    """The session containing this Eastern minute-of-day, or None (the halt).

    Left-open, right-closed to match close-stamped bars. Asia wraps midnight.
    """
    for spec in cfg.SESSIONS:
        start, end = spec["start"], spec["end"]
        if end <= start:  # wraps past midnight
            inside = minute_of_day > start or minute_of_day <= end
        else:
            inside = start < minute_of_day <= end
        if inside:
            return spec["name"]
    return None


class Sessions(Indicator):
    """Publishes the current session, whether it just opened, and its extremes."""

    id = "sessions"
    fields = ("session", "session_new", "session_high", "session_low", "session_open")
    depends = ()

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._session: str | None = None
        self._open: float | None = None
        self._high: float | None = None
        self._low: float | None = None

    def update(self, event, upstream=None) -> dict:
        ts = getattr(event, "ts", None)
        if ts is None:
            raise Unavailable("sessions needs a timestamped event")

        name = session_for(_minute_of_day(ts))

        # A new session begins whenever the name changes - including into and out
        # of the halt (name None), so the reopen always starts a clean session.
        is_new = name != self._session
        if is_new:
            self._session = name
            self._open = getattr(event, "open", None)
            self._high = getattr(event, "high", None)
            self._low = getattr(event, "low", None)
        else:
            high, low = getattr(event, "high", None), getattr(event, "low", None)
            if high is not None:
                self._high = high if self._high is None else max(self._high, high)
            if low is not None:
                self._low = low if self._low is None else min(self._low, low)

        return {
            "session": self._session,
            "session_new": is_new,
            "session_high": self._high,
            "session_low": self._low,
            "session_open": self._open,
        }
