"""The structure points: where price turned, confirmed only once it had -
plus the high and low that are true right now, before anything is confirmed.

**A swing is known late, by construction.** The bar that makes a high does not
announce itself; you learn it was a high only after price falls away from it by
``RETRACE x range_scale``. So this indicator publishes on the *confirming* bar
and names the *earlier* bar that made the extreme. That lag is not a defect to
be engineered away - it is the price of not looking ahead.

**But the extremes exist on every bar.** While price runs, nothing confirms and
``swing`` stays silent - yet a highest-high-so-far is sitting right there in this
object, ratcheting up with each new high. Publishing only on confirmation made
the screen go blank during exactly the move you most want to watch. So the two
rails are published too:

    extreme_high / extreme_low   the standing high and low, on every bar
    hunting                      which of them is still provisional
    retrace                      how far price has pulled back from it
    trigger                      the price at which the provisional one confirms

One rail is **live**: the one in the hunting direction, extending as new extremes
print. The other is **frozen** at the last confirmed swing. When the retrace
finally arrives, the live rail freezes into a swing point and the roles swap.

``retrace`` is that distance measured from the live rail to this bar's close, in
``range_scale`` units, so it is dimensionless: double every price in the data and
it does not move. It is a *conservative* view of the trigger, which tests this
bar's low (or high), not its close - so a swing can confirm on a bar whose
``retrace`` reads a little under ``RETRACE``. And on a bar that makes a new
extreme it can read high without confirming anything, because a bar that extends
the extreme is never tested against it.

**The rails are not swings, and must never be traded as though they were.** A
provisional extreme is "the highest price so far". A swing is "a high that price
turned away from". Both are built only from bars at or before now - neither can
look ahead - but they are different objects, and a rule that confuses them is
honest about time and wrong about meaning.

They live here rather than in an indicator of their own because they *are* this
state machine's state. A separate indicator would have to run the same machine a
second time to see them, which is the duplication the registry exists to prevent.

Levels, trend, higher-highs and lower-lows are still elsewhere: what a *sequence*
of swings means is a different job (see ``legs`` and ``breaks``), and those read
this indicator rather than re-deriving it.
"""

from __future__ import annotations

import logging

from src.config.indicators import swing as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

HIGH, LOW = "high", "low"

_NO_SWING = {"swing": None, "swing_price": None, "swing_time": None}


class Swing(Indicator):
    """Confirmed swing points, and the provisional extremes they come from."""

    id = "swing"
    fields = ("swing", "swing_price", "swing_time",
              "extreme_high", "extreme_high_time",
              "extreme_low", "extreme_low_time",
              "hunting", "retrace", "trigger")
    depends = ("range_scale",)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._dir = 0                          # +1 hunting a high, -1 hunting a low
        self._high: float | None = None        # live while hunting a high
        self._high_time: int | None = None
        self._low: float | None = None         # live while hunting a low
        self._low_time: int | None = None

    def update(self, event, upstream=None) -> dict:
        scale = (upstream or {}).get("range_scale")
        if scale is None:
            # range_scale refused, so we must too. A threshold without a scale is
            # a threshold in points, which is the one thing this must never be.
            raise Unavailable("swing needs range_scale; it is still warming up")

        threshold = cfg.RETRACE * scale
        ts = int(event.ts.timestamp())
        row = dict(_NO_SWING)

        if self._high is None:
            # The first bar has nothing to retrace from. Anchor both rails on it
            # and start looking for a swing high; the choice is arbitrary and
            # affects only whether the very first swing found is a high or a low.
            self._dir = 1
            self._high, self._high_time = event.high, ts
            self._low, self._low_time = event.low, ts

        elif self._dir > 0:
            if event.high > self._high:
                # Still making highs. A bar that extends the extreme cannot also
                # confirm it - hence the elif, not a second if.
                self._high, self._high_time = event.high, ts
            elif self._high - event.low >= threshold:
                row = {"swing": HIGH, "swing_price": self._high,
                       "swing_time": self._high_time}
                # The high freezes where it stands; the low rail goes live here.
                self._dir = -1
                self._low, self._low_time = event.low, ts

        else:
            if event.low < self._low:
                self._low, self._low_time = event.low, ts
            elif event.high - self._low >= threshold:
                row = {"swing": LOW, "swing_price": self._low,
                       "swing_time": self._low_time}
                self._dir = 1
                self._high, self._high_time = event.high, ts

        row.update(self._rails(event, scale, threshold))
        return row

    def _rails(self, event, scale: float, threshold: float) -> dict:
        """Both extremes as they stand at the end of this bar, and the retrace."""
        hunting_high = self._dir > 0
        live = self._high if hunting_high else self._low
        # Distance from the live rail to where the bar actually closed. Never
        # negative: the close cannot exceed the extreme, which includes this
        # bar's own high and low.
        retrace = (live - event.close) if hunting_high else (event.close - live)

        return {
            "extreme_high": self._high,
            "extreme_high_time": self._high_time,
            "extreme_low": self._low,
            "extreme_low_time": self._low_time,
            "hunting": HIGH if hunting_high else LOW,
            "retrace": retrace / scale,
            # Where the provisional extreme becomes a swing. A bar whose LOW
            # reaches this (or whose HIGH does, hunting a low) confirms it. It
            # rides up under a rising high, so it says what has to happen next.
            "trigger": (live - threshold) if hunting_high else (live + threshold),
        }
