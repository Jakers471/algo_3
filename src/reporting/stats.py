"""Aggregate Trades into performance metrics, split All / Long / Short.

One job: the numbers you judge a strategy by (mirrors NT8's summary), plus our
own honesty flag - how many outcomes rest on the adverse-first same-bar
assumption. Sharpe/Sortino here are per-trade (not annualized); labeled as such.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from src.backtest.engine import Trade
from src.backtest.bracket import Direction


@dataclass
class Stats:
    scope: str            # "all" | "long" | "short"
    n_trades: int
    wins: int
    losses: int
    evens: int
    win_rate: float
    net_profit: float
    gross_profit: float
    gross_loss: float
    commission: float
    profit_factor: float
    avg_trade: float
    avg_win: float
    avg_loss: float
    win_loss_ratio: float
    largest_win: float
    largest_loss: float
    max_consec_wins: int
    max_consec_losses: int
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    avg_bars: float
    avg_mae: float
    avg_mfe: float
    avg_etd: float
    ambiguous: int
    ambiguous_pct: float
    same_bar: int


def _std(xs: list[float], mean: float) -> float:
    if len(xs) < 2:
        return 0.0
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


def _max_streak(trades: list[Trade], win: bool) -> int:
    best = cur = 0
    for t in trades:
        is_win = t.pnl_dollars > 0
        if is_win == win:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def compute(trades: list[Trade], starting_capital: float, scope: str) -> Stats:
    n = len(trades)
    wins = [t for t in trades if t.pnl_dollars > 0]
    losses = [t for t in trades if t.pnl_dollars < 0]
    evens = [t for t in trades if t.pnl_dollars == 0]
    pnls = [t.pnl_dollars for t in trades]
    gross_profit = sum(t.pnl_dollars for t in wins)
    gross_loss = -sum(t.pnl_dollars for t in losses)  # positive magnitude
    net = sum(pnls)

    equity = peak = starting_capital
    max_dd = 0.0
    for t in trades:
        equity += t.pnl_dollars
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    mean = net / n if n else 0.0
    downside = [min(x, 0.0) for x in pnls]
    dmean = sum(downside) / n if n else 0.0
    sd = _std(pnls, mean)
    dsd = _std(downside, dmean)

    return Stats(
        scope=scope,
        n_trades=n,
        wins=len(wins),
        losses=len(losses),
        evens=len(evens),
        win_rate=len(wins) / n if n else 0.0,
        net_profit=net,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        commission=sum(t.commission for t in trades),
        profit_factor=(gross_profit / gross_loss) if gross_loss else float("inf"),
        avg_trade=mean,
        avg_win=gross_profit / len(wins) if wins else 0.0,
        avg_loss=-gross_loss / len(losses) if losses else 0.0,
        win_loss_ratio=(gross_profit / len(wins)) / (gross_loss / len(losses))
        if wins and losses else 0.0,
        largest_win=max((t.pnl_dollars for t in wins), default=0.0),
        largest_loss=min((t.pnl_dollars for t in losses), default=0.0),
        max_consec_wins=_max_streak(trades, True),
        max_consec_losses=_max_streak(trades, False),
        expectancy=mean,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd / peak * 100 if peak else 0.0,
        sharpe=mean / sd if sd else 0.0,
        sortino=mean / dsd if dsd else 0.0,
        avg_bars=sum(t.bars for t in trades) / n if n else 0.0,
        avg_mae=sum(t.mae for t in trades) / n if n else 0.0,
        avg_mfe=sum(t.mfe for t in trades) / n if n else 0.0,
        avg_etd=sum(t.etd for t in trades) / n if n else 0.0,
        ambiguous=sum(t.ambiguous for t in trades),
        ambiguous_pct=sum(t.ambiguous for t in trades) / n * 100 if n else 0.0,
        same_bar=sum(t.same_bar for t in trades),
    )


def compute_all(trades: list[Trade], starting_capital: float) -> dict[str, Stats]:
    """Compute stats for all trades and the long / short subsets."""
    longs = [t for t in trades if t.direction is Direction.LONG]
    shorts = [t for t in trades if t.direction is Direction.SHORT]
    return {
        "all": compute(trades, starting_capital, "all"),
        "long": compute(longs, starting_capital, "long"),
        "short": compute(shorts, starting_capital, "short"),
    }


def _json_safe(v):
    """inf/nan are not valid JSON - emit null instead."""
    return None if (isinstance(v, float) and not math.isfinite(v)) else v


def write_json(stats: dict[str, Stats], path: str | Path) -> None:
    payload = {scope: {k: _json_safe(v) for k, v in asdict(s).items()} for scope, s in stats.items()}
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_text(stats: dict[str, Stats], path: str | Path) -> None:
    Path(path).write_text(_text_table(stats), encoding="utf-8")


_ROWS = [
    ("Total net profit", "net_profit", "$"),
    ("Gross profit", "gross_profit", "$"),
    ("Gross loss", "gross_loss", "$"),
    ("Commission", "commission", "$"),
    ("Profit factor", "profit_factor", "f"),
    ("Sharpe (per-trade)", "sharpe", "f"),
    ("Sortino (per-trade)", "sortino", "f"),
    ("Max drawdown", "max_drawdown", "$"),
    ("Max drawdown %", "max_drawdown_pct", "%"),
    ("Total # trades", "n_trades", "d"),
    ("Winning / losing", "wins", "wl"),
    ("Percent profitable", "win_rate", "pct"),
    ("Avg trade", "avg_trade", "$"),
    ("Avg winning trade", "avg_win", "$"),
    ("Avg losing trade", "avg_loss", "$"),
    ("Ratio avg win/loss", "win_loss_ratio", "f"),
    ("Max consec winners", "max_consec_wins", "d"),
    ("Max consec losers", "max_consec_losses", "d"),
    ("Largest winning trade", "largest_win", "$"),
    ("Largest losing trade", "largest_loss", "$"),
    ("Avg bars in trade", "avg_bars", "f"),
    ("Avg MAE", "avg_mae", "$"),
    ("Avg MFE", "avg_mfe", "$"),
    ("Avg ETD", "avg_etd", "$"),
    ("Ambiguous (adverse-first)", "ambiguous", "d"),
    ("Ambiguous %", "ambiguous_pct", "%"),
    ("Same-bar exits", "same_bar", "d"),
]


def _fmt(kind: str, s: Stats, key: str) -> str:
    v = getattr(s, key)
    if kind == "$":
        return f"${v:,.2f}"
    if kind == "%":
        return f"{v:.2f}%"
    if kind == "pct":
        return f"{v * 100:.2f}%"
    if kind == "f":
        return "inf" if v == float("inf") else f"{v:.2f}"
    if kind == "d":
        return f"{v:,}"
    if kind == "wl":
        return f"{s.wins}W / {s.losses}L"
    return str(v)


def _text_table(stats: dict[str, Stats]) -> str:
    scopes = ["all", "long", "short"]
    header = f"{'Performance':<26}{'All':>16}{'Long':>16}{'Short':>16}"
    lines = [header, "-" * len(header)]
    for label, key, kind in _ROWS:
        row = f"{label:<26}"
        for sc in scopes:
            row += f"{_fmt(kind, stats[sc], key):>16}"
        lines.append(row)
    return "\n".join(lines) + "\n"
