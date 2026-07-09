"""Price went one way while the aggressors went the other.

One job: say whether this bar closed against its own order flow, and which side
did the absorbing.

A bar closes green while sellers were the net aggressors: every seller who
crossed the spread was met by a resting buyer, and price lifted anyway. Somebody
was absorbing. The reverse - red on net buying - is a resting seller. Measured on
this data, it happens on 17.9% of bars, and the candle alone cannot show it: two
bars matched to within a tick of body, six ticks of range and 2.5% of volume
differed by 1,326 contracts of delta.

**This names a fact, not an edge.** The bar did close against its flow; whether
that predicts anything is a question for a backtest that does not exist yet. The
field exists so the rows can answer it.

Depends on ``orderflow``: it reads ``delta`` rather than recomputing it, which is
what the registry's dependency ordering is for. When order flow is unavailable -
every NT8 bar file, 2005-2025 - so is absorption, and it raises ``Unavailable``
rather than deciding that a bar with no recorded aggressor absorbed nothing.
"""

from __future__ import annotations

import logging

from src.config.indicators import absorption as cfg
from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)

BUY, SELL = "buy", "sell"


class Absorption(Indicator):
    """Publishes whether the bar closed against its flow, and who absorbed."""

    id = "absorption"
    fields = ("absorption", "absorption_side")
    depends = ("orderflow",)

    def reset(self) -> None:
        """Stateless: each bar is judged on itself alone."""

    def update(self, event, upstream=None) -> dict:
        delta = (upstream or {}).get("delta")
        if delta is None:
            # orderflow refused, so we must too. A bar with no recorded aggressor
            # did not "absorb nothing" - nobody wrote down what happened.
            raise Unavailable("absorption needs delta; this bar carries no order flow")

        body = event.close - event.open
        if body == 0 or delta == 0 or not self._significant(event, delta):
            return {"absorption": False, "absorption_side": None}

        # Buyers absorbed: price rose while sellers were the net aggressors.
        if body > 0 and delta < 0:
            return {"absorption": True, "absorption_side": BUY}
        # Sellers absorbed: price fell while buyers were the net aggressors.
        if body < 0 and delta > 0:
            return {"absorption": True, "absorption_side": SELL}

        return {"absorption": False, "absorption_side": None}

    @staticmethod
    def _significant(event, delta: float) -> bool:
        """Filter out disagreements too small or too thin to mean anything."""
        if abs(delta) < cfg.MIN_ABS_DELTA:
            return False
        if event.volume < cfg.MIN_VOLUME:
            return False
        if cfg.MIN_DELTA_RATIO > 0 and event.volume > 0:
            if abs(delta) / event.volume < cfg.MIN_DELTA_RATIO:
                return False
        return True
