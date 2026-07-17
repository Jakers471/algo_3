"""A short list of named simple moving averages, each its own line and colour.

One job: publish, on every bar, the value of each ENABLED line in
config.indicators.ma.LINES - and its previous value, so the drawing layer can
stroke a segment from where the line sat to where it sits now without keeping
any state of its own.

Where this differs from `ribbon`. Ribbon is a fan of many evenly-spaced SMAs
meant to be read as one shape, coloured by slope. This indicator is a short,
explicit list of named periods - "the 50", or "the 50 and the 200" - each
independently switchable in config and drawn in its own fixed colour, the way
a trader actually asks for named averages rather than a fan.

Same honesty rule as every SMA in this codebase: a mean of thirty closes
standing in for a mean of fifty is a different number, not a rougher one, so a
line publishes None until it has exactly `period` closes.
"""

from __future__ import annotations

import logging
from collections import deque

from src.config.indicators import ma as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)


class MA(Indicator):
    """Publishes the value of each enabled named moving average, and its previous value."""

    id = "ma"
    fields = ("ma", "ma_prev")
    depends = ()

    about = {
        "ma": ("price", "One value per line in config ACTIVE (the ENABLED entries of "
               "LINES, in order). Each is the simple mean of the last `period` closes, "
               "or None while that line still has fewer than `period` closes to average. "
               "A drawing, not a reading: the lines are on the chart, not in the table."),
        "ma_prev": ("price", "The same lines' values on the PREVIOUS bar, carried "
                    "forward so the chart can draw a segment from the last bar to this "
                    "one without keeping its own state."),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        periods = [line["period"] for line in cfg.ACTIVE]
        self._periods = periods
        self._windows: list[deque[float]] = [deque() for _ in periods]
        self._sums: list[float] = [0.0 for _ in periods]
        self._prev: list[float | None] = [None] * len(periods)

    def update(self, event, upstream=None) -> dict:
        close = getattr(event, "close", None)
        if close is None:
            raise Unavailable("ma needs a bar close; this event has none")

        values: list[float | None] = []
        for i, period in enumerate(self._periods):
            window, self._sums[i] = self._windows[i], self._sums[i] + close
            window.append(close)
            if len(window) > period:
                self._sums[i] -= window.popleft()
            # Exactly `period` closes, or nothing yet: a partial average is a
            # different number, not a rougher one.
            values.append(self._sums[i] / period if len(window) == period else None)

        prev, self._prev = self._prev, values
        return {"ma": values, "ma_prev": prev}
