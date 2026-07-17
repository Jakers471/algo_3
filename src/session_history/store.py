"""Read the packed session-history table: where does a value rank, live.

One job: load what build.py wrote and answer two questions - "what percentile
is this value at, against history at the same elapsed bar of the same
session" and "what fraction of a typical full session's travel has this one
spent so far." Small (a few hundred KB), so the whole table loads into memory
once and stays there - no memmap needed at this size.
"""

from __future__ import annotations

import numpy as np

from src.config import session_history as cfg

_METRIC_INDEX = {"range": 0, "travel": 1, "volume": 2}

_CACHE: dict[tuple, dict] = {}


class NotBuilt(FileNotFoundError):
    """The session-history table has not been built. Run: python -m src.cli.session_history"""


def _load(symbol: str, timeframe: str) -> dict:
    key = (symbol, timeframe)
    if key not in _CACHE:
        from src.session_history.build import path
        p = path(symbol, timeframe)
        if not p.exists():
            raise NotBuilt(
                f"no session-history table for {symbol} {timeframe}; "
                f"run: python -m src.cli.session_history")
        with np.load(p) as npz:
            _CACHE[key] = {k: npz[k] for k in npz.files}
    return _CACHE[key]


def percentile_rank(symbol: str, timeframe: str, session: str, elapsed_bar: int,
                    metric: str, value: float) -> float | None:
    """Where ``value`` ranks (0..1) against history at this exact elapsed bar.

    None if the table has not been built, this session name was never tracked,
    or this session has already run deeper than anything in the historical
    dataset ever did (nothing to compare against).
    """
    data = _load(symbol, timeframe)
    table = data.get(f"table_{session}")
    if table is None or elapsed_bar < 1 or elapsed_bar > table.shape[0]:
        return None
    breakpoints = table[elapsed_bar - 1, _METRIC_INDEX[metric]]
    if np.isnan(breakpoints).all():
        return None
    rank = np.interp(value, breakpoints, cfg.PERCENTILES)
    return float(rank) / 100.0


def travel_budget(symbol: str, timeframe: str, session: str,
                  travel_so_far_x_scale: float) -> float | None:
    """travel_so_far / a typical (median) FULL session's travel.

    The fuel gauge: how much of a normal day's ground has this session
    already covered. >1.0 means it has already travelled further than a
    typical full session does start to finish - a late break in a session
    like that is spending distance the "average day" ledger no longer has.
    """
    data = _load(symbol, timeframe)
    median = data.get(f"median_final_travel_{session}")
    if median is None or not np.isfinite(median) or median <= 0:
        return None
    return float(travel_so_far_x_scale / median)
