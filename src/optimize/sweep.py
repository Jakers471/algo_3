"""Run a parameter grid over one window and rank the results by objective.

One job: for each param combo, backtest it on the given bars, score it, and
return the combos sorted best-first. Reuses the engine and stats unchanged -
this is just orchestration over the same atomic backtest.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest import engine
from src.optimize import grid as grid_mod
from src.optimize import objective as obj_mod
from src.reporting import stats as stats_mod
from src.reporting.stats import Stats
from src.strategy import registry


@dataclass
class SweepResult:
    params: dict
    score: float
    stats: Stats


def sweep(
    bars: pd.DataFrame,
    strategy_name: str,
    param_grid: dict,
    objective: str,
    symbol: str,
    *,
    size: int = 1,
    min_trades: int = 0,
    starting_capital: float = 0.0,
) -> list[SweepResult]:
    """Backtest every grid combo on ``bars``; return them ranked best-first."""
    results: list[SweepResult] = []
    for params in grid_mod.expand(param_grid):
        strat = registry.build(strategy_name, params)
        trades = engine.run(bars, strat, symbol, size=size)
        st = stats_mod.compute(trades, starting_capital, "all")
        results.append(SweepResult(params, obj_mod.score(st, objective, min_trades), st))
    results.sort(key=lambda r: r.score, reverse=True)
    return results
