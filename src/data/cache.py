"""Persist expensive derived series to disk, keyed by data + params.

One job: compute-once / read-many for the rolling_consolidation mask - the slow
part of VA-breakout. It is computed on the FULL symbol/timeframe dataset, so
every backtest window and every walk-forward fold reindexes into it with correct
trailing context (no per-slice warmup gap) and pays the cost only once. Cached
under the git-ignored cache/ dir; delete it to recompute after a data change.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.data import loader
from src.indicators.grade import rolling_state

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"


def state_series(symbol: str, timeframe: str, state_window: int,
                 e_cut: float, a_cut: float, n_rows: int) -> pd.Series:
    """The full-dataset per-bar GRADE state, as a string Series indexed by timestamp.

    Loads from cache/ if present; otherwise computes it on the whole symbol/
    timeframe dataset (one-time), caches it, and returns it. The CONSOLIDATION mask
    and the regime census both derive from this one series.
    """
    key = f"state_{symbol}_{timeframe}_sw{state_window}_e{e_cut}_a{a_cut}_r{n_rows}.parquet"
    path = CACHE_DIR / key
    if path.exists():
        logger.info("Regime state: cache hit (%s)", key)
        return pd.read_parquet(path)["state"]

    logger.info("Regime state: cache miss - computing on full %s %s (one-time)", symbol, timeframe)
    bars = loader.load_raw(symbol, timeframe)
    states = rolling_state(bars, state_window, e_cut, a_cut, n_rows)
    s = pd.Series(states, index=bars.index, name="state")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    s.to_frame().to_parquet(path)
    logger.info("Regime state: cached %d bars -> %s", len(s), key)
    return s
