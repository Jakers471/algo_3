"""How big a bar is *here, now* - the unit every other threshold is measured in.

One job: publish the typical bar range at this timeframe, as a rolling median.

**Why this indicator exists at all.** NQ's median 30s range moved between 4.50
and 14.25 points across 29 months - a 3.17x swing, 31% coefficient of variation.
Any threshold written in points is therefore correct for one volatility regime
and wrong for the next, silently. Measured in multiples of *this* field instead,
"big" means the same thing in a sleepy August and in April 2025.

**Why a rolling estimate can work.** Bar range is strongly persistent: on 5m NQ
bars, the median range of the last 60 bars correlates 0.65 with the median of
the next 60. Were range independent bar to bar, that would be 0.00 and nothing
adaptive would be possible - you would be stuck with a constant. The market
tells you how big its bars are about to be.

**Why a median and not a mean.** One violent bar should not redefine normal. The
p99 bar is about five times the median at every timeframe; a mean would chase it.

**Why it refuses at the start.** Fewer than ``MIN_BARS`` and this is not a rougher
number, it is a *different* number - and every threshold downstream would be
quietly wrong for the opening minutes of every replay. It raises ``Unavailable``,
so the row records None. None means "nobody could say yet". Zero would mean "the
bars have no size", which is a claim about the market.

**And why it refuses on a dead tape.** The median range really can be zero: on
0.21% of tick-built 30s bars, most of the last 60 bars printed a single price and
never moved off it. Zero is not a small unit, it is *no unit* - a threshold
measured in it is zero, and ``swing`` would then confirm a structure point on
almost every bar of a market that is not moving. Dividing by it is worse. So a
zero scale is Unavailable too, and everything downstream honestly reports absent
until the tape wakes up.

It is deliberately not drawn. A denominator is not a picture.
"""

from __future__ import annotations

import logging
from bisect import insort
from collections import deque

from src.config.indicators import range_scale as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)


class RangeScale(Indicator):
    """Publishes the rolling median bar range, or nothing while it warms up."""

    id = "range_scale"
    fields = ("range_scale",)
    depends = ()

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # Arrival order (to know which value ages out) and sorted order (to take
        # a median without re-sorting). WINDOW is small, so the O(n) removal from
        # the sorted list costs less than keeping a heap honest.
        self._arrivals: deque[float] = deque()
        self._sorted: list[float] = []

    def update(self, event, upstream=None) -> dict:
        high = getattr(event, "high", None)
        low = getattr(event, "low", None)
        if high is None or low is None:
            raise Unavailable("range_scale needs a bar; this event has no high/low")

        self._observe(high - low)

        if len(self._arrivals) < cfg.MIN_BARS:
            raise Unavailable(
                f"range_scale has seen {len(self._arrivals)} of {cfg.MIN_BARS} bars")

        median = self._median()
        if median <= 0:
            # A dead tape: most of the window printed one price and never left
            # it. Zero is no unit at all - a threshold measured in it is zero,
            # and a ratio measured in it is undefined.
            raise Unavailable("range_scale is zero; the tape has not moved")

        return {"range_scale": median}

    def _observe(self, bar_range: float) -> None:
        """Record this bar's range and age out anything past the window."""
        self._arrivals.append(bar_range)
        insort(self._sorted, bar_range)
        if len(self._arrivals) > cfg.WINDOW:
            self._sorted.remove(self._arrivals.popleft())

    def _median(self) -> float:
        n = len(self._sorted)
        mid = n // 2
        if n % 2:
            return self._sorted[mid]
        return (self._sorted[mid - 1] + self._sorted[mid]) / 2.0
