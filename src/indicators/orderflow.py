"""Signed volume: who crossed the spread, and by how much.

One job: publish the order flow a bar carries - ``delta`` (aggressive buys minus
aggressive sells), the two sides that make it, and the number of prints.

It computes nothing. The work was done once, exactly, when the bars were rebuilt
from ticks: a trade printing at the ask is a buyer lifting the offer, at the bid
a seller hitting it (only 0.000474% of volume prints strictly between, and that
joins neither side). This indicator simply lifts those fields into the snapshot
row so the table can show them and later indicators can depend on them.

**It refuses on bars that have none.** The NT8 bar files (2005-2025) record total
volume but never the aggressor - that information was destroyed by aggregation
and no transformation recovers it. Fed those, this raises ``Unavailable`` and the
row records ``None``. It does not return zero. Zero would mean "buying and
selling were perfectly balanced", which is a claim about the market; None means
"nobody wrote it down", which is a claim about the data. A backtest would believe
the first one.

Measured on real data, this is not a small distinction: the candle explains only
56% of delta, and 17.9% of bars close in the opposite direction to their net
order flow.
"""

from __future__ import annotations

import logging

from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)


class OrderFlow(Indicator):
    """Publishes delta / buy_volume / sell_volume / trades, or nothing at all."""

    id = "orderflow"
    fields = ("delta", "buy_volume", "sell_volume", "trades")
    depends = ()

    def reset(self) -> None:
        """Stateless: each bar carries its own flow. Nothing to forget."""

    def update(self, event, upstream=None) -> dict:
        delta = getattr(event, "delta", None)
        if delta is None:
            raise Unavailable(
                "this bar carries no order flow; use a tick-rebuilt dataset (NQT)")

        return {
            "delta": delta,
            "buy_volume": getattr(event, "buy_volume", None),
            "sell_volume": getattr(event, "sell_volume", None),
            "trades": getattr(event, "trades", None),
        }
