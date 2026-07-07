"""The backtest loop: walk bars, arm entries, resolve exits, record trades.

One job: drive a single-position bracket backtest. It asks the strategy for
resting stop-entry levels, uses fills.py to decide fills, honors the session
hold policy (audit: gap_awareness) using the loader's ``gap_before`` marks, and
emits a list of Trades. All money math uses point_value (audit: back_adjustment).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src.backtest import fills
from src.config import backtest as bt_cfg
from src.config import instruments
from src.strategy.bracket import Bracket, Direction

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: Direction
    entry_price: float
    exit_price: float
    size: int
    pnl_points: float
    pnl_dollars: float
    reason: str          # "stop" | "target" | "session"
    ambiguous: bool      # resolved by adverse-first (same-bar stop+target)
    same_bar: bool       # entered and exited on the same bar


def run(bars: pd.DataFrame, strategy, symbol: str, *, size: int = 1) -> list[Trade]:
    """Run the strategy over prepared bars and return the closed trades.

    ``size`` is fixed for now (the risk engine will size later). Long-only: the
    engine arms the strategy's buy-stop when flat.
    """
    inst = instruments.get(symbol)
    tick, pv = inst.tick_size, inst.point_value
    slip = bt_cfg.SLIPPAGE_TICKS
    commission = bt_cfg.COMMISSION_PER_SIDE
    allow_hold = bt_cfg.ALLOW_OVERNIGHT_HOLD and bt_cfg.ALLOW_WEEKEND_HOLD

    levels = strategy.entry_levels(bars).to_numpy()
    p = strategy.params

    trades: list[Trade] = []
    pending: Bracket | None = None      # armed resting entry
    pos = None                          # open position dict, or None

    times = bars.index
    o = bars["open"].to_numpy()
    h = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    c = bars["close"].to_numpy()
    gap = bars["gap_before"].to_numpy()

    def close_trade(exit_time, exit_price, reason, ambiguous, same_bar):
        pts = (exit_price - pos["entry_price"]) if pos["dir"] is Direction.LONG \
            else (pos["entry_price"] - exit_price)
        dollars = pts * pv * size - 2 * commission * size
        trades.append(Trade(
            pos["entry_time"], exit_time, pos["dir"], pos["entry_price"],
            exit_price, size, pts, dollars, reason, ambiguous, same_bar,
        ))

    for i in range(len(bars)):
        bar = fills.Bar(o[i], h[i], low[i], c[i])

        # 1. Session force-flat: a gap starts a new session on this bar; if we
        #    held across it and policy forbids, exit at the last pre-gap close.
        if pos is not None and gap[i] and not allow_hold:
            close_trade(times[i - 1], c[i - 1], "session", False, False)
            pos, pending = None, None

        # 2. In a position: try to exit on this bar.
        if pos is not None:
            ex = fills.exit_fill(pos["dir"], pos["stop"], pos["target"], bar, tick, slip)
            if ex is not None:
                close_trade(times[i], ex.price, ex.reason, ex.ambiguous, False)
                pos = None

        # 3. Flat with an armed entry: try to trigger it (and maybe exit same bar).
        if pos is None and pending is not None:
            fill = fills.entry_fill(pending, bar, tick, slip)
            if fill is not None:
                pos = {
                    "dir": pending.direction, "entry_time": times[i], "entry_price": fill,
                    "stop": pending.stop_price(fill), "target": pending.target_price(fill),
                }
                pending = None
                ex = fills.exit_fill(pos["dir"], pos["stop"], pos["target"], bar, tick, slip)
                if ex is not None:  # same-bar entry and exit
                    close_trade(times[i], ex.price, ex.reason, ex.ambiguous, True)
                    pos = None

        # 4. Flat and nothing armed: ask the strategy to arm from this bar.
        if pos is None and pending is None:
            level = levels[i]
            if level == level:  # not NaN
                pending = Bracket(strategy.direction, float(level), p.stop_points, p.target_points)

    logger.info(
        "Backtest %s: %d trades (%d ambiguous same-bar, %d same-bar exits)",
        symbol, len(trades),
        sum(t.ambiguous for t in trades), sum(t.same_bar for t in trades),
    )
    return trades
