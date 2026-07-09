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
    """

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return self.close - self.open
