"""The market event vocabulary: what every source emits and every indicator eats.

One job: define the timestamped things that arrive in order. Nothing here knows
where an event came from - a bar read off Parquet, a tick replayed from the
stitched tick file, and a trade pushed over the live SignalR hub are all just
events. That is the whole point: an indicator written against these types runs
unchanged in backtest, in replay, and live.

Every event carries ``ts`` as a tz-aware UTC datetime - market time, not wall
time. Indicators are fed events in ts order and may only ever see the past, so
an indicator cannot look ahead by construction rather than by convention.

Today only BarClose exists, because bars are the only source wired up. Trade and
Quote arrive with their sources (BUILD_PLAN.md phases 4-5); they are not written
here in advance, because an event type with no producer is a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BarClose:
    """A completed bar. Timestamped at its CLOSE - it covers ``(ts - step, ts]``.

    This matches the NT8 Parquet store exactly (verified: 1m bars aggregate into
    5m bars, OHLC and volume, using closed='right'/label='right'). A bar stamped
    ``T`` is therefore fully known at ``T``, so revealing it at ``T`` leaks nothing.

    The order-flow fields are ``None`` on any bar that cannot supply them. A bar
    file records total volume but never which side was the aggressor - that is
    destroyed by aggregation and no transformation recovers it. ``None`` means
    absent; it never means zero. An indicator that needs them and finds None must
    raise ``Unavailable`` rather than compute on a fabricated number.
    """

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Present only on bars rebuilt from ticks (data/NQT/).
    delta: float | None = None
    buy_volume: float | None = None
    sell_volume: float | None = None
    trades: float | None = None

    #: Volume at price: ``(prices, volume, buy_volume)``, prices ascending.
    #:
    #: A bar knows its total volume, its high and its low. It does not know WHERE
    #: between them the contracts changed hands - that is in the ticks and nowhere
    #: else. Spreading a bar's volume across its range would be a fabrication, so
    #: this is None on any bar file and an indicator that needs it must refuse.
    vap: tuple | None = None

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return self.close - self.open

    @property
    def has_order_flow(self) -> bool:
        return self.delta is not None

    @property
    def has_volume_at_price(self) -> bool:
        return self.vap is not None
