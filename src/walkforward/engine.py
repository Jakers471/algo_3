"""Orchestrate a walk-forward run: optimize IS, test OOS, stitch the OOS.

One job: walk the folds. For each, sweep the param grid on the in-sample
window, pick the best, run those params on the out-of-sample window, and
collect the OOS trades. The stitched OOS trades are re-sequenced into one
continuous equity curve - the honest result. Walk-forward efficiency compares
mean OOS score to mean IS score.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from statistics import mean

import pandas as pd

from src.backtest import engine as bt_engine
from src.backtest.engine import Trade
from src.config import backtest as bt_cfg
from src.optimize import objective as obj_mod
from src.optimize import sweep as sweep_mod
from src.reporting import stats as stats_mod
from src.strategy import registry
from src.walkforward import folds as folds_mod
from src.walkforward.wfaspec import WFASpec

logger = logging.getLogger(__name__)


@dataclass
class FoldResult:
    fold: folds_mod.Fold
    best_params: dict
    is_score: float
    oos_score: float
    n_oos_trades: int


@dataclass
class WFAResult:
    fold_results: list[FoldResult]
    oos_trades: list[Trade]   # stitched, re-sequenced
    wfe: float


def _restitch(trades: list[Trade]) -> None:
    """Re-number the stitched OOS trades and rebuild the running cum PnL."""
    trades.sort(key=lambda t: t.exit_time)
    cum = 0.0
    for i, t in enumerate(trades, 1):
        t.num = i
        cum += t.pnl_dollars
        t.cum_pnl = cum


def _wfe(fold_results: list[FoldResult]) -> float:
    is_scores = [fr.is_score for fr in fold_results if math.isfinite(fr.is_score)]
    oos_scores = [fr.oos_score for fr in fold_results if math.isfinite(fr.oos_score)]
    if not is_scores or not oos_scores:
        return 0.0
    m_is = mean(is_scores)
    return mean(oos_scores) / m_is if m_is else 0.0


def run(bars: pd.DataFrame, spec: WFASpec, *, progress=None) -> WFAResult:
    index = bars.index
    the_folds = folds_mod.generate(index, spec.is_days, spec.oos_days, spec.step_days, spec.anchored)
    if not the_folds:
        raise ValueError("No folds fit the data span - shorten is_days/oos_days.")
    logger.info("Walk-forward: %d folds, %d combos each", len(the_folds),
                len(sweep_mod.grid_mod.expand(spec.param_grid)))

    cap = bt_cfg.STARTING_CAPITAL
    fold_results: list[FoldResult] = []
    stitched: list[Trade] = []

    for f in the_folds:
        is_bars = bars[(index >= f.is_start) & (index < f.is_end)]
        oos_bars = bars[(index >= f.oos_start) & (index < f.oos_end)]

        ranked = sweep_mod.sweep(
            is_bars, spec.strategy, spec.param_grid, spec.objective, spec.symbol,
            timeframe=spec.timeframe, size=spec.size, min_trades=spec.min_trades,
            starting_capital=cap,
        )
        best = ranked[0]

        strat = registry.build(spec.strategy, best.params, spec.symbol, spec.timeframe)
        oos_trades = bt_engine.run(oos_bars, strat, spec.symbol, size=spec.size)
        oos_stats = stats_mod.compute(oos_trades, cap, "all")
        oos_score = obj_mod.score(oos_stats, spec.objective, 0)

        fold_results.append(FoldResult(f, best.params, best.score, oos_score, len(oos_trades)))
        stitched.extend(oos_trades)
        if progress is not None:
            progress.update(f.num)

    _restitch(stitched)
    return WFAResult(fold_results, stitched, _wfe(fold_results))
