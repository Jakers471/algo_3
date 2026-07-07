"""Score a backtest's Stats by a named objective (higher = better).

One job: map an objective name to a single number the optimizer maximizes.
Combos below ``min_trades`` score -inf so a lucky 1-trade result can't win, and
non-finite scores (e.g. profit factor with zero losses) are rejected the same
way - both are selection-bias traps.
"""

from __future__ import annotations

import math

from src.reporting.stats import Stats

OBJECTIVES = {
    "net_profit": lambda s: s.net_profit,
    "profit_factor": lambda s: s.profit_factor,
    "sharpe": lambda s: s.sharpe,
    "sortino": lambda s: s.sortino,
    "expectancy": lambda s: s.expectancy,
    "win_rate": lambda s: s.win_rate,
}


def score(stats: Stats, objective: str, min_trades: int = 0) -> float:
    """The objective value for these stats, or -inf if it fails the guards."""
    try:
        fn = OBJECTIVES[objective]
    except KeyError:
        raise KeyError(f"Unknown objective {objective!r}; known: {list(OBJECTIVES)}") from None
    if stats.n_trades < min_trades:
        return float("-inf")
    v = fn(stats)
    return v if math.isfinite(v) else float("-inf")
