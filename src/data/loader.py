"""Read raw OHLCV bars from the NT8 Parquet store.

One job: locate a symbol/timeframe Parquet file and load it into a DataFrame
with a tz-aware UTC index and lowercase OHLCV columns. Plumbing only - it
knows where the files live and how to read them, not how to clean them
(that is prepare.py's job).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# data/ lives at the repo root: src/data/loader.py -> parents[2].
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Symbols with a per-symbol folder: data/<SYM>/<SYM>_<TF>.parquet.
SYMBOLS = ("NQ", "ES")

# Bar spacing per timeframe - the base cadence used to detect session gaps.
TIMEFRAMES: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "60m": "60min",
    "1d": "1D",
}

EXPECTED_COLUMNS = ["open", "high", "low", "close", "volume"]


def path_for(symbol: str, timeframe: str) -> Path:
    """Resolve the Parquet path for a symbol/timeframe (no I/O)."""
    return DATA_DIR / symbol / f"{symbol}_{timeframe}.parquet"


def load_raw(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load one symbol/timeframe Parquet as raw UTC-indexed OHLCV bars."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {timeframe!r}; known: {list(TIMEFRAMES)}")
    fp = path_for(symbol, timeframe)
    if not fp.exists():
        raise FileNotFoundError(f"No data file for {symbol} {timeframe}: {fp}")

    logger.debug("Reading %s", fp)
    df = _normalize(pd.read_parquet(fp), fp)
    logger.info(
        "Loaded %s %s: %d bars, %s -> %s",
        symbol, timeframe, len(df), df.index[0], df.index[-1],
    )
    return df


def _normalize(df: pd.DataFrame, fp: Path) -> pd.DataFrame:
    """Enforce the canonical shape: UTC tz-aware index, lowercase OHLCV cols."""
    df = df.rename(columns=str.lower)
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{fp.name} missing columns {missing}; has {list(df.columns)}")
    df = df[EXPECTED_COLUMNS]

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(f"{fp.name} index is not a DatetimeIndex: {type(df.index).__name__}")
    # Keep everything UTC internally (audit: timezone, required).
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()
    return df
