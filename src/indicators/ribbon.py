"""A fan of moving averages, each a rolling mean of the close.

One job: publish, on every bar, the value of each ribbon line - and the value it
held on the previous bar, so the drawing layer can colour each line segment by
which way it just moved.

Why two fields and not one. A moving average is a price; whether it is rising or
falling is a fact about *two* bars, not one, and the chart draws a line from the
previous bar's value to this one. Rather than have the drawing layer remember the
last row (it is stateless by design, one row in, shapes out), the indicator - which
IS a state machine - carries the previous values forward and publishes both. The
line and its slope then fall straight out of a single row.

Why simple averages. An SMA of period N is exactly the mean of the last N closes,
and it is absent until N closes exist. That refusal is deliberate and shared with
every other indicator here: a mean of three closes standing in for a mean of a
hundred is a different number, not a rougher one, and every line that leans on it
would be quietly wrong for the opening bars of a window. A line still warming up
publishes None for its slot, and the chart simply does not draw it yet.

It never looks ahead: each average is over closes at or before the current bar,
so the fan at bar T is exactly what it would have been had you played into T.
"""

from __future__ import annotations

import logging
from collections import deque

from src.config.indicators import ribbon as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)


class Ribbon(Indicator):
    """Publishes the value of each moving-average line, and its previous value."""

    id = "ribbon"
    fields = ("ribbon", "ribbon_prev")
    depends = ()

    about = {
        "ribbon": ("price", "One value per moving-average line, in the order of "
                   "config PERIODS (short to long). Each is the simple mean of the last "
                   "`period` closes, or None while that line still has fewer than "
                   "`period` closes to average. A drawing, not a reading: the fan is on "
                   "the chart, not in the table."),
        "ribbon_prev": ("price", "The same lines' values on the PREVIOUS bar, carried "
                        "forward so the chart can colour each segment by its slope - "
                        "green where the line rose, red where it fell. Detail: it is "
                        "half of a line the chart draws."),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # One window per period, each with its running sum so a mean costs no
        # re-addition. The previous bar's published values, so the slope of every
        # line is available from a single row.
        self._windows: list[deque[float]] = [deque() for _ in cfg.PERIODS]
        self._sums: list[float] = [0.0 for _ in cfg.PERIODS]
        self._prev: list[float | None] = [None] * len(cfg.PERIODS)

    def update(self, event, upstream=None) -> dict:
        close = getattr(event, "close", None)
        if close is None:
            raise Unavailable("ribbon needs a bar close; this event has none")

        values: list[float | None] = []
        for i, period in enumerate(cfg.PERIODS):
            window, self._sums[i] = self._windows[i], self._sums[i] + close
            window.append(close)
            if len(window) > period:
                self._sums[i] -= window.popleft()
            # Exactly `period` closes, or nothing yet: a partial average is a
            # different number, not a rougher one.
            values.append(self._sums[i] / period if len(window) == period else None)

        prev, self._prev = self._prev, values
        return {"ribbon": values, "ribbon_prev": prev}
