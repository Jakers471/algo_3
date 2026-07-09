"""Break of structure: a swing level that price finally took out.

One job: hold the most recent unbroken swing high and swing low, and say when
price closed beyond one of them.

A swing high standing above the market is a level nobody has been willing to pay.
The bar that closes above it says somebody now is. That is a **break of
structure** - bullish when a swing high goes, bearish when a swing low goes. The
level is then spent: it fires once and is cleared, and the next swing of that
kind replaces it. A level that kept re-breaking on every bar would be a drawing,
not an event.

**Close, not wick, by default.** A high that pierces a level and closes back
below it is a rejection of the level, not a break of it, and calling both the
same thing throws away the distinction the bar was drawing for you. ``USE_CLOSE``
turns this into the wick test if you want to measure the difference.

Depends on ``swing``: the levels *are* swing points, read rather than recomputed.
It refuses until a swing level exists, because "no break" before there is
anything to break is a claim about the market that nobody is entitled to make.
"""

from __future__ import annotations

import logging

from src.config.indicators import breaks as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

UP, DOWN = "up", "down"

_NOTHING = {"bos": None, "bos_level": None, "bos_time": None}


class Breaks(Indicator):
    """Publishes a break of structure on the bar that takes a swing level out."""

    id = "breaks"
    fields = ("bos", "bos_level", "bos_time")
    depends = ("swing",)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._high: tuple[float, int] | None = None   # (price, time), unbroken
        self._low: tuple[float, int] | None = None

    def update(self, event, upstream=None) -> dict:
        up = upstream or {}

        if self._high is None and self._low is None and up.get("swing") is None:
            raise Unavailable("breaks has no swing level to break yet")

        # Test THIS bar against the levels standing before it. A swing confirmed
        # on this bar cannot be broken by it: confirmation required price to
        # retrace away from the extreme, so it is on the wrong side.
        result = self._test(event)

        self._absorb(up)
        return result

    def _test(self, event) -> dict:
        above = event.close if cfg.USE_CLOSE else event.high
        below = event.close if cfg.USE_CLOSE else event.low

        if self._high is not None and above > self._high[0]:
            level, time = self._high
            self._high = None          # spent: it fires once
            return {"bos": UP, "bos_level": level, "bos_time": time}

        if self._low is not None and below < self._low[0]:
            level, time = self._low
            self._low = None
            return {"bos": DOWN, "bos_level": level, "bos_time": time}

        return dict(_NOTHING)

    def _absorb(self, upstream: dict) -> None:
        """A newly confirmed swing becomes the standing level of its kind."""
        swing = upstream.get("swing")
        if swing is None:
            return
        point = (upstream["swing_price"], upstream["swing_time"])
        if swing == "high":
            self._high = point
        else:
            self._low = point
