"""The structure points: where price turned, confirmed only once it had.

One job: emit a swing high or a swing low when price has retraced far enough
from the running extreme to prove the extreme was one.

**A swing is known late, by construction.** The bar that makes a high does not
announce itself; you learn it was a high only after price falls away from it by
``RETRACE x range_scale``. So this indicator publishes on the *confirming* bar
and names the *earlier* bar that made the extreme. That lag is not a defect to
be engineered away - it is the price of not looking ahead. It is also exactly
why a ladder of timeframes exists: the 15m rung confirms about six swings in a
session and always after the fact, while the 30s rung confirms 178 and sees the
turn while it is still worth something. Permission from above, timing from below.

**The threshold adapts; the shape does not.** The retrace is measured in
multiples of ``range_scale``, never in points, so the same code finds the same
structure in a quiet market and a violent one. Double every price in the data and
this indicator emits the identical swings, because both the threshold and the
retrace double with it. That invariance is pinned by a test.

Depends on ``range_scale`` and refuses while it is warming up: a swing threshold
computed from a scale that does not exist yet would just be a threshold in points.

Levels, trend, higher-highs and lower-lows are **not** here. A swing point is a
fact about where price turned; what a sequence of them *means* is a different job
with a different lifetime, and it will read this indicator rather than re-derive
it - which is what the registry's dependency ordering is for.
"""

from __future__ import annotations

import logging

from src.config.indicators import swing as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

HIGH, LOW = "high", "low"

_NOTHING = {"swing": None, "swing_price": None, "swing_time": None}


class Swing(Indicator):
    """Publishes a confirmed swing point, or nothing at all on most bars."""

    id = "swing"
    fields = ("swing", "swing_price", "swing_time")
    depends = ("range_scale",)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._dir = 0             # +1 tracking a high, -1 tracking a low
        self._extreme: float | None = None
        self._extreme_time: int | None = None

    def update(self, event, upstream=None) -> dict:
        scale = (upstream or {}).get("range_scale")
        if scale is None:
            # range_scale refused, so we must too. A threshold without a scale is
            # a threshold in points, which is the one thing this must never be.
            raise Unavailable("swing needs range_scale; it is still warming up")

        threshold = cfg.RETRACE * scale
        ts = int(event.ts.timestamp())

        if self._extreme is None:
            # The first bar has nothing to retrace from. Anchor on its high and
            # start looking for a swing high; the choice is arbitrary and affects
            # only whether the very first swing found is a high or a low.
            self._dir, self._extreme, self._extreme_time = 1, event.high, ts
            return dict(_NOTHING)

        if self._dir > 0:
            if event.high > self._extreme:
                # Still making highs. A bar that extends the extreme cannot also
                # confirm it - hence the elif, not a second if.
                self._extreme, self._extreme_time = event.high, ts
            elif self._extreme - event.low >= threshold:
                confirmed = self._turn(HIGH, low=event.low, ts=ts)
                return confirmed
        else:
            if event.low < self._extreme:
                self._extreme, self._extreme_time = event.low, ts
            elif event.high - self._extreme >= threshold:
                confirmed = self._turn(LOW, high=event.high, ts=ts)
                return confirmed

        return dict(_NOTHING)

    def _turn(self, kind: str, *, ts: int, high: float | None = None,
              low: float | None = None) -> dict:
        """Confirm the extreme we were tracking, then start tracking the other way."""
        price, time = self._extreme, self._extreme_time

        if kind == HIGH:
            self._dir, self._extreme, self._extreme_time = -1, low, ts
        else:
            self._dir, self._extreme, self._extreme_time = 1, high, ts

        # The swing is stamped with the bar that MADE it, which is at or before
        # the bar being processed. It is never in the future.
        return {"swing": kind, "swing_price": price, "swing_time": time}
