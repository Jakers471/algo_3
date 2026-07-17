"""Build the historical percentile table session_stats reads at runtime.

One job: walk every London/NY session in a dataset once, and for every
elapsed bar-index into a session, record cumulative range/travel (both in
range_scale units) and volume so far - then reduce each (session, bar-index,
metric) cell to a set of percentile breakpoints. Written once; session_
history/store.py loads what this writes and answers "where does TODAY's
number rank against history at this same point in the session."

Why percentile, not points, and not even points-over-range_scale. NQ's median
30s range moved 4.50 -> 14.25 across 29 months (range_scale.py). Dividing by
range_scale corrects for the regime the market is in RIGHT NOW - but it does
not correct for whether the DISTRIBUTION range_scale is itself drawn from has
drifted over the life of the dataset. A percentile rank against the SAME
dataset's history, at the SAME elapsed bar count, sidesteps that: a value is
not "big" or "small" in the abstract, only relative to what usually happens by
this point in a London or NY session, in the same x-range_scale units
session_stats already reports elsewhere on the card.

    python -m src.cli.session_history --symbol NQT --timeframe 5m
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import session_history as cfg
from src.config.indicators import session_stats as ss_cfg
from src.data.loader import load_raw
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.range_scale import RangeScale
from src.indicators.sessions import session_runs

logger = logging.getLogger(__name__)


def path(symbol: str, timeframe: str):
    cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return cfg.CACHE_DIR / f"{symbol}_{timeframe}.npz"


def _scales(bars: pd.DataFrame) -> np.ndarray:
    """range_scale at every bar, NaN while warming up or on a dead tape.

    Flows continuously across session boundaries - range_scale is a rolling
    window over calendar time, agnostic to which session a bar belongs to,
    exactly as it runs live.
    """
    scale_of = RangeScale()
    out = np.full(len(bars), np.nan)
    o, h = bars["open"].to_numpy(), bars["high"].to_numpy()
    lo, c = bars["low"].to_numpy(), bars["close"].to_numpy()
    v = bars["volume"].to_numpy()
    for i, ts in enumerate(bars.index):
        event = BarClose(ts=ts, open=o[i], high=h[i], low=lo[i], close=c[i], volume=v[i])
        try:
            out[i] = scale_of.update(event)["range_scale"]
        except Unavailable:
            pass
    return out


def _cumulative(idx: list[int], high: np.ndarray, low: np.ndarray,
                volume: np.ndarray, scale: np.ndarray) -> tuple:
    """Per elapsed bar of one session run: cumulative range/travel (x scale) and volume.

    ``range`` is the run's own high-to-low span so far - a rolling max minus a
    rolling min - never a sum of the bars in it; ``travel`` sums each bar's
    OWN (high - low). The same distinction session_stats.py's _window_stats
    keeps, at session scope instead of a sliding window's.
    """
    h, lo, v, s = high[idx], low[idx], volume[idx], scale[idx]
    cum_high = np.maximum.accumulate(h)
    cum_low = np.minimum.accumulate(lo)
    cum_range = cum_high - cum_low
    cum_travel = np.cumsum(h - lo)
    cum_volume = np.cumsum(v)
    with np.errstate(invalid="ignore", divide="ignore"):
        range_x = cum_range / s
        travel_x = cum_travel / s
    return range_x, travel_x, cum_volume


def build(symbol: str, timeframe: str, *, explore_only: bool = False) -> dict:
    """``explore_only`` drops every sealed session (see session_history/split.py).

    The default (full history) is right for the LIVE card - sealed sessions
    are the past, relative to live. It is WRONG for any evaluation on sealed
    data: a table built over the full set bakes the vault's own distribution
    into the reading being evaluated against it. Rebuild with explore_only
    before that day.
    """
    bars = load_raw(symbol, timeframe)[["open", "high", "low", "close", "volume"]]
    runs = session_runs(bars, ss_cfg.TRACKED_SESSIONS)
    if explore_only:
        from src.session_history import split
        runs = [(name, idx) for name, idx in runs
                if not split.is_sealed(int(bars.index[idx[0]].timestamp()))]
    scale = _scales(bars)
    high, low = bars["high"].to_numpy(), bars["low"].to_numpy()
    volume = bars["volume"].to_numpy()

    # One bucket per (session name, elapsed bar): every session's own value at
    # that point, collected across the whole dataset, ready to reduce to
    # percentiles. A python dict of lists, not a preallocated array - a
    # session's own length varies bar to bar (gaps, holidays), so the max
    # elapsed bar count is not known until every run has been walked.
    buckets: dict[str, dict[int, list]] = {name: {} for name in ss_cfg.TRACKED_SESSIONS}
    final_travel: dict[str, list[float]] = {name: [] for name in ss_cfg.TRACKED_SESSIONS}
    sessions_seen = {name: 0 for name in ss_cfg.TRACKED_SESSIONS}

    for name, idx in runs:
        range_x, travel_x, cum_volume = _cumulative(idx, high, low, volume, scale)
        valid = np.flatnonzero(np.isfinite(range_x) & np.isfinite(travel_x))
        if len(valid) == 0:
            continue
        sessions_seen[name] += 1
        for elapsed in valid:
            buckets[name].setdefault(int(elapsed) + 1, []).append(
                (range_x[elapsed], travel_x[elapsed], float(cum_volume[elapsed])))
        # The LAST valid point this session reached, for the travel budget
        # gauge - not necessarily the run's final bar, if range_scale had not
        # warmed up yet at the very end of a short session.
        final_travel[name].append(float(travel_x[valid[-1]]))

    payload: dict[str, np.ndarray] = {}
    for name in ss_cfg.TRACKED_SESSIONS:
        max_bar = max(buckets[name], default=0)
        table = np.full((max_bar, 3, len(cfg.PERCENTILES)), np.nan)
        for elapsed, rows in buckets[name].items():
            arr = np.array(rows)
            for metric in range(3):
                table[elapsed - 1, metric] = np.percentile(arr[:, metric], cfg.PERCENTILES)
        payload[f"table_{name}"] = table
        payload[f"median_final_travel_{name}"] = np.array(
            np.median(final_travel[name]) if final_travel[name] else np.nan)
        logger.info("%s: %d sessions, %d bars deep, median final travel %.2f x range_scale",
                    name, sessions_seen[name], max_bar,
                    payload[f"median_final_travel_{name}"])

    payload["percentiles"] = cfg.PERCENTILES
    out = path(symbol, timeframe)
    np.savez(out, **payload)
    logger.info("Wrote %s", out)
    return {"path": out, "sessions": sessions_seen}
