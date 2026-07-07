"""Persist OHLCV bars to human-readable CSV.

One job: turn the API's raw bar dicts (keys t, o, h, l, c, v) into a tidy CSV
with columns timestamp, open, high, low, close, volume — sorted oldest-first,
de-duplicated. Files land in the top-level data/ dir (git-ignored) as
``<SYMBOL>_<TF>.csv`` to sit beside the existing NT8 exports.
"""

from __future__ import annotations

import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

# API bar key -> tidy column name.
_COLUMNS = {"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
_ORDER = ["timestamp", "open", "high", "low", "close", "volume"]


def bars_to_frame(bars: list[dict]) -> pd.DataFrame:
    """Convert raw API bars to a tidy OHLCV DataFrame, oldest-first."""
    df = pd.DataFrame(bars).rename(columns=_COLUMNS)
    df = df[_ORDER]
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def save_bars_csv(symbol: str, timeframe: str, bars: list[dict], data_dir: str) -> str:
    """Write bars to ``data_dir/<SYMBOL>_<TF>.csv``; return the path."""
    os.makedirs(data_dir, exist_ok=True)
    df = bars_to_frame(bars)
    path = os.path.join(data_dir, f"{symbol}_{timeframe}.csv")
    df.to_csv(path, index=False)
    logger.info("Saved %d rows -> %s", len(df), path)
    return path
