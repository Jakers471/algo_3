"""Read the ribbon's shape and name the regime the market is in.

One job: turn the 32-line fan into three dimensionless readings - alignment,
agreement, width - and a regime label built from them.

Why it reads the ribbon rather than recomputing anything. The fan already holds
everything about trend the moving averages can say; the regime is a *view* of
that state, not a new measurement. So this indicator depends on `ribbon` (the
line values, and their previous values, for the slopes) and on `range_scale` (the
ruler the width is measured in), and it publishes numbers, never prices.

The three readings, each in [-1, +1] or in multiples of range_scale:

    alignment  the lines stacked in period order. Over the 31 adjacent pairs,
               +1 for each shorter-over-longer, -1 for the reverse. +1 is a clean
               up-trend, -1 a clean down-trend, 0 a scrambled fan. This is the
               sortedness of the permutation - zero inversions is a trend.
    agreement  the lines sloping the same way this bar. +1 all rising, -1 all
               falling. It leads alignment: velocity turns before position does.
    width      (max line - min line) / range_scale. The fan's flare, and by the
               (N-1)/2 lag geometry that is proportional to price velocity. Wide
               is a trend with conviction; near zero is a squeeze.

The label is then: a trend (up/down) when the lines are stacked AND flared; a
transition when the fan has pinched shut (a regime loading); chop otherwise. A
new label must hold CONFIRM_BARS bars before it is adopted, so the regime does
not flicker every time price grazes a threshold.

Honesty. It refuses (`Unavailable`) until the fan is fully warm - every line and
its previous value present - and until range_scale exists. A regime read off half
a fan is a different number, not a rougher one, and a width with no ruler is
points masquerading as a ratio. No lookahead: every reading is of the current
bar's state.
"""

from __future__ import annotations

import logging

from src.config.indicators import regime as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

UP, DOWN, CHOP, TRANSITION = "up", "down", "chop", "transition"


class Regime(Indicator):
    """Publishes the ribbon's alignment, agreement, width, and a regime label."""

    id = "regime"
    fields = ("ribbon_align", "ribbon_agree", "ribbon_width", "regime", "regime_new")
    depends = ("ribbon", "range_scale")

    about = {
        "ribbon_align": ("-1..+1", "How well the ribbon is stacked in period order, over "
                         "its 31 adjacent pairs. +1 short-over-long throughout (a clean "
                         "up-trend), -1 fully inverted (a clean down-trend), 0 a scrambled "
                         "fan. The sortedness of the fan: zero inversions is a trend."),
        "ribbon_agree": ("-1..+1", "The share of ribbon lines rising this bar minus the "
                         "share falling. +1 all rising, -1 all falling. It leads alignment "
                         "- a line's slope turns before its position in the stack does."),
        "ribbon_width": ("x range_scale", "The fan's flare: (highest line - lowest line) "
                         "over range_scale. By the (N-1)/2 lag geometry it is proportional "
                         "to price velocity - wide is a trend with conviction, near zero is "
                         "a squeeze. In range_scale so a cutoff survives a change of regime."),
        "regime": ("up | down | chop | transition | None", "The market's state read off the "
                   "fan: a trend (up/down) when the lines are stacked and flared, a "
                   "transition when the fan has pinched shut, chop otherwise. Absent until "
                   "the fan is fully warm."),
        "regime_new": ("boolean", "True on the bar the regime CHANGED - what the chart draws "
                       "a rule on. Detail: scaffolding for the drawing, not a reading."),
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # The adopted regime, and the candidate waiting out its confirmation.
        self._regime: str | None = None
        self._candidate: str | None = None
        self._count = 0

    def update(self, event, upstream=None) -> dict:
        up = upstream or {}
        lines = up.get("ribbon")
        prev = up.get("ribbon_prev")
        scale = up.get("range_scale")

        if scale is None or not lines or not prev:
            raise Unavailable("regime needs a warm fan and a scale")
        if any(v is None for v in lines) or any(v is None for v in prev):
            # A regime read off half a fan is a different number, not a rougher
            # one. Wait until every line - and its previous value, for the slope -
            # is present.
            raise Unavailable("regime waits for every ribbon line to warm up")

        align = self._alignment(lines)
        agree = self._agreement(lines, prev)
        width = (max(lines) - min(lines)) / scale

        new = self._adopt(self._classify(align, width))
        return {
            "ribbon_align": align,
            "ribbon_agree": agree,
            "ribbon_width": width,
            "regime": self._regime,
            "regime_new": new,
        }

    # --- the readings -------------------------------------------------------

    @staticmethod
    def _alignment(lines) -> float:
        """+1 short-over-long throughout, -1 fully inverted, 0 scrambled."""
        pairs = len(lines) - 1
        score = sum((a > b) - (a < b) for a, b in zip(lines, lines[1:]))
        return score / pairs

    @staticmethod
    def _agreement(lines, prev) -> float:
        """The share of lines rising minus the share falling, this bar."""
        n = len(lines)
        score = sum((now > was) - (now < was) for now, was in zip(lines, prev))
        return score / n

    # --- the label ----------------------------------------------------------

    def _classify(self, align: float, width: float) -> str:
        """One bar's instantaneous regime, before confirmation."""
        if width < cfg.WIDTH_PINCH:
            return TRANSITION            # a squeeze is a regime loading, not a trend
        if width >= cfg.WIDTH_TREND and align >= cfg.ALIGN_TREND:
            return UP
        if width >= cfg.WIDTH_TREND and align <= -cfg.ALIGN_TREND:
            return DOWN
        return CHOP

    def _adopt(self, cls: str) -> bool:
        """Adopt a new regime only once it has held CONFIRM_BARS bars.

        Returns True on the bar the adopted regime changed - never on the first
        one it is established, which is a fact about the indicator waking up, not
        about the market turning.
        """
        if self._regime is None:
            self._regime = self._candidate = cls
            self._count = 0
            return False

        if cls == self._regime:
            self._candidate, self._count = cls, 0
            return False

        if cls == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = cls, 1

        if self._count >= cfg.CONFIRM_BARS:
            self._regime = cls
            self._count = 0
            return True
        return False
