"""Read the packed session-history table: where does a value rank, live.

One job: load what build.py wrote and answer two questions - "what percentile
is this value at, against history at the same elapsed bar of the same
session" and "what fraction of a typical full session's travel has this one
spent so far." Small (a few hundred KB), so the whole table loads into memory
once and stays there - no memmap needed at this size.

**Which history is not a detail; it is the answer.** A percentile means nothing
without the population behind it, so ``split_label`` is required on every call
and has no default. ``FULL`` is right for the live card, where the sealed third
genuinely is the past. ``EXPLORE`` is the only honest answer anywhere the
sealed sessions have not happened yet - a backtest, a study, any evaluation -
because a table built over everything tells a 2024 bar where it ranks against
sessions that had not occurred, and that does not fail loudly. It just looks
good. Asking a caller to name the population is the cheapest possible guard
against the one bug here that hides.
"""

from __future__ import annotations

import numpy as np

from src.config import session_history as cfg

# Which population a table was built from. Distinct from split.py's
# EXPLORE/SEALED, which label a SESSION: a session is sealed or not, while a
# table is built from explore-only history or from all of it. The two
# vocabularies meet but are not the same word.
EXPLORE, FULL = "explore", "full"

_METRIC_INDEX = {"range": 0, "travel": 1, "volume": 2}

_CACHE: dict[tuple, dict] = {}


class NotBuilt(FileNotFoundError):
    """The session-history table has not been built. Run: python -m src.cli.session_history"""


def _load(symbol: str, timeframe: str, split_label: str) -> dict:
    key = (symbol, timeframe, split_label)
    if key not in _CACHE:
        from src.session_history.build import path
        p = path(symbol, timeframe, split_label)
        if not p.exists():
            extra = ("" if split_label != "explore"
                     else " --explore-only")
            raise NotBuilt(
                f"no {split_label} session-history table for {symbol} "
                f"{timeframe}; run: python -m src.cli.session_history"
                f" --symbol {symbol} --timeframe {timeframe}{extra}")
        with np.load(p) as npz:
            _CACHE[key] = {k: npz[k] for k in npz.files}
    return _CACHE[key]


def describe(symbol: str, timeframe: str, split_label: str) -> dict:
    """What this table was built from. The table's own word, not the caller's.

    ``build_from`` is written into the payload at build time, so this survives
    a file being renamed or rebuilt behind a reader's back - the label in the
    filename is a convenience; this is the receipt.
    """
    data = _load(symbol, timeframe, split_label)
    return {
        "built_from": str(data["built_from"]) if "built_from" in data else "unknown",
        "cutoff_utc": str(data["cutoff_utc"]) if "cutoff_utc" in data else "",
        "sessions_used": (data["sessions_used"].tolist()
                          if "sessions_used" in data else None),
    }


def percentile_rank(symbol: str, timeframe: str, session: str, elapsed_bar: int,
                    metric: str, value: float, *, split_label: str) -> float | None:
    """Where ``value`` ranks (0..1) against history at this exact elapsed bar.

    None if the table has not been built, this session name was never tracked,
    or this session has already run deeper than anything in the historical
    dataset ever did (nothing to compare against).
    """
    data = _load(symbol, timeframe, split_label)
    table = data.get(f"table_{session}")
    if table is None or elapsed_bar < 1 or elapsed_bar > table.shape[0]:
        return None
    breakpoints = table[elapsed_bar - 1, _METRIC_INDEX[metric]]
    if np.isnan(breakpoints).all():
        return None
    rank = np.interp(value, breakpoints, cfg.PERCENTILES)
    return float(rank) / 100.0


def travel_budget(symbol: str, timeframe: str, session: str,
                  travel_so_far_x_scale: float, *,
                  split_label: str) -> float | None:
    """travel_so_far / a typical (median) FULL session's travel.

    The fuel gauge: how much of a normal day's ground has this session
    already covered. >1.0 means it has already travelled further than a
    typical full session does start to finish - a late break in a session
    like that is spending distance the "average day" ledger no longer has.
    """
    data = _load(symbol, timeframe, split_label)
    median = data.get(f"median_final_travel_{session}")
    if median is None or not np.isfinite(median) or median <= 0:
        return None
    return float(travel_so_far_x_scale / median)
