"""The staircase: the leg that runs from one structure point to the next.

One job: when ``swing`` confirms a structure point, publish the leg that just
closed - where it started, where it ended, and which way it went.

This is the relationship *between* swing points, which ``swing`` itself
deliberately refuses to know: its docstring says a swing point is a fact about
where price turned, and what a sequence of them means is a different job. This
is that job, in its smallest form. Higher-highs, lower-lows and trend state read
these legs; they do not re-derive them.

Swings alternate high, low, high, low, so the direction of a leg is simply
whether it ended above where it began. A leg is emitted on the bar that
*confirmed* its far end, which is later than the bar that made it - that lag is
inherited from ``swing`` and is the price of not looking ahead.

It refuses until it has seen two swings. One point is not a leg, and reporting
"no leg" before a second swing exists would be a claim we cannot make.
"""

from __future__ import annotations

import logging

from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

UP, DOWN = "up", "down"

_NOTHING = {"leg": None, "leg_from_price": None, "leg_from_time": None,
            "leg_to_price": None, "leg_to_time": None}


class Legs(Indicator):
    """Publishes the leg between the last two confirmed swing points."""

    id = "legs"
    fields = ("leg", "leg_from_price", "leg_from_time", "leg_to_price", "leg_to_time")
    depends = ("swing",)

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._prev: tuple[float, int] | None = None   # (price, time)

    def update(self, event, upstream=None) -> dict:
        up = upstream or {}
        swing = up.get("swing")

        if swing is None:
            # No swing confirmed on this bar. That is only an honest "no leg"
            # once a leg is possible at all - before the first swing lands we
            # know nothing, and None must mean absent, not empty.
            if self._prev is None:
                raise Unavailable("legs has not seen a swing yet")
            return dict(_NOTHING)

        point = (up["swing_price"], up["swing_time"])
        previous, self._prev = self._prev, point

        if previous is None:
            raise Unavailable("legs needs two swings to draw one leg")

        from_price, from_time = previous
        to_price, to_time = point
        return {
            "leg": UP if to_price > from_price else DOWN,
            "leg_from_price": from_price,
            "leg_from_time": from_time,
            "leg_to_price": to_price,
            "leg_to_time": to_time,
        }
