"""The backtest loop: walk bars, arm entries, resolve exits, record trades.

One job: drive a single-position bracket backtest. It asks the strategy for
resting stop-entry levels, uses fills.py to decide fills, honors the session
hold policy (audit: gap_awareness) using the loader's ``gap_before`` marks, and
emits a list of Trades. All money math uses point_value (audit: back_adjustment).

Per trade it also tracks the excursions NT8-style reports need: MAE (max
adverse), MFE (max favorable), ETD (give-back from the best point), and bars.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src.backtest import fills
from src.config import backtest as bt_cfg
from src.config import instruments
from src.backtest.bracket import Bracket, Direction

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    num: int
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: Direction
    entry_price: float
    exit_price: float
    size: int
    pnl_points: float
    pnl_dollars: float       # net of commission
    commission: float        # round-trip commission ($)
    reason: str              # "stop" | "target" | "session"
    ambiguous: bool          # resolved by adverse-first (same-bar stop+target)
    same_bar: bool           # entered and exited on the same bar
    bars: int                # bars held (entry..exit inclusive)
    mae: float               # max adverse excursion ($, positive magnitude)
    mfe: float               # max favorable excursion ($)
    etd: float               # end-trade drawdown: give-back from MFE ($)
    cum_pnl: float = 0.0     # running net PnL after this trade ($)


def run(bars: pd.DataFrame, strategy, symbol: str, *, size: int = 1, progress=None) -> list[Trade]:
    """Run the strategy over prepared bars and return the closed trades.

    ``size`` is fixed for now (the risk engine will size later). Long-only: the
    engine arms the strategy's buy-stop when flat. ``progress`` is an optional
    object with ``.update(i)`` for a CLI progress bar.
    """
    inst = instruments.get(symbol)
    tick, pv = inst.tick_size, inst.point_value
    slip = bt_cfg.SLIPPAGE_TICKS
    comm_side = bt_cfg.COMMISSION_PER_SIDE
    allow_hold = bt_cfg.ALLOW_OVERNIGHT_HOLD and bt_cfg.ALLOW_WEEKEND_HOLD

    signals = strategy.entry_signals(bars)
    dirs = signals["direction"].to_numpy()          # Direction or None per bar
    entries = signals["entry_stop"].to_numpy()      # absolute trigger price
    stops = signals["stop_price"].to_numpy()        # absolute stop level
    targets = signals["target_price"].to_numpy()    # absolute target level

    times = bars.index
    o = bars["open"].to_numpy()
    h = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    c = bars["close"].to_numpy()
    gap = bars["gap_before"].to_numpy()
    n = len(bars)

    trades: list[Trade] = []
    pending: Bracket | None = None
    pos: dict | None = None
    cum = 0.0

    def excursion(long: bool, entry: float, hi: float, lo: float) -> tuple[float, float]:
        """(favorable, adverse) point moves for this bar, positive = in-favor/against."""
        if long:
            return hi - entry, entry - lo
        return entry - lo, hi - entry

    def close_trade(exit_i: int, exit_price: float, reason: str, ambiguous: bool, same_bar: bool):
        nonlocal cum
        long = pos["dir"] is Direction.LONG
        pts = (exit_price - pos["entry_price"]) if long else (pos["entry_price"] - exit_price)
        commission = 2 * comm_side * size
        dollars = pts * pv * size - commission
        mfe = pos["mfe_pts"] * pv * size
        mae = pos["mae_pts"] * pv * size
        etd = max(pos["mfe_pts"] - pts, 0.0) * pv * size
        cum += dollars
        # Cast numpy scalars (prices come from .to_numpy()) to Python floats so
        # downstream stats/JSON stay clean.
        trades.append(Trade(
            num=len(trades) + 1,
            entry_time=pos["entry_time"], exit_time=times[exit_i], direction=pos["dir"],
            entry_price=float(pos["entry_price"]), exit_price=float(exit_price), size=size,
            pnl_points=float(pts), pnl_dollars=float(dollars), commission=float(commission),
            reason=reason, ambiguous=bool(ambiguous), same_bar=same_bar,
            bars=int(exit_i - pos["entry_index"] + 1),
            mae=float(mae), mfe=float(mfe), etd=float(etd), cum_pnl=float(cum),
        ))

    for i in range(n):
        bar = fills.Bar(o[i], h[i], low[i], c[i])

        # 1. Session force-flat: a gap starts a new session on this bar; if we
        #    held across it and policy forbids, exit at the last pre-gap close.
        if pos is not None and gap[i] and not allow_hold:
            close_trade(i - 1, c[i - 1], "session", False, False)
            pos, pending = None, None

        # 2. In a position: track excursion on this bar, then try to exit.
        if pos is not None:
            fav, adv = excursion(pos["dir"] is Direction.LONG, pos["entry_price"], h[i], low[i])
            pos["mfe_pts"] = max(pos["mfe_pts"], fav)
            pos["mae_pts"] = max(pos["mae_pts"], adv)
            ex = fills.exit_fill(pos["dir"], pos["stop"], pos["target"], bar, tick, slip)
            if ex is not None:
                close_trade(i, ex.price, ex.reason, ex.ambiguous, False)
                pos = None

        # 3. Flat with an armed entry: try to trigger it (and maybe exit same bar).
        if pos is None and pending is not None:
            fill = fills.entry_fill(pending, bar, tick, slip)
            if fill is not None:
                pos = {
                    "dir": pending.direction, "entry_time": times[i], "entry_price": fill,
                    "entry_index": i, "stop": pending.stop_price,
                    "target": pending.target_price, "mfe_pts": 0.0, "mae_pts": 0.0,
                }
                pending = None
                fav, adv = excursion(pos["dir"] is Direction.LONG, fill, h[i], low[i])
                pos["mfe_pts"], pos["mae_pts"] = fav, adv
                ex = fills.exit_fill(pos["dir"], pos["stop"], pos["target"], bar, tick, slip)
                if ex is not None:  # same-bar entry and exit
                    close_trade(i, ex.price, ex.reason, ex.ambiguous, True)
                    pos = None

        # 4. Flat and nothing armed: arm the strategy's signal for this bar.
        if pos is None and pending is None:
            d = dirs[i]
            e = entries[i]
            if d is not None and e == e:  # has a direction and a non-NaN entry level
                pending = Bracket(d, float(e), float(stops[i]), float(targets[i]))

        if progress is not None and (i & 0x3FFF) == 0:
            progress.update(i)

    if progress is not None:
        progress.update(n)

    logger.info(
        "Backtest %s: %d trades (%d ambiguous same-bar, %d same-bar exits)",
        symbol, len(trades),
        sum(t.ambiguous for t in trades), sum(t.same_bar for t in trades),
    )
    return trades
