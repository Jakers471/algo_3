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
# NQ/ES are the NT8 bar files. NQT is rebuilt from ticks and is a SEPARATE
# dataset - different span, different back-adjustment anchor. Never mix them.
SYMBOLS = ("NQ", "ES", "NQT")

# Bar spacing per timeframe - the base cadence used to detect session gaps.
# 15s exists only for NQT: bars cannot be subdivided, only ticks can.
TIMEFRAMES: dict[str, str] = {
    "15s": "15s",
    "30s": "30s",
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "60m": "60min",
    "4h": "4h",
    "1d": "1D",
}

EXPECTED_COLUMNS = ["open", "high", "low", "close", "volume"]

# Order flow, present only in datasets rebuilt from ticks. A bar file records
# total volume but not which side was the aggressor, and that information is
# destroyed by aggregation - so these columns are absent, not zero, on NQ/ES.
ORDER_FLOW_COLUMNS = ["delta", "buy_volume", "sell_volume", "trades"]


def path_for(symbol: str, timeframe: str) -> Path:
    """Resolve the Parquet path for a symbol/timeframe (no I/O)."""
    return DATA_DIR / symbol / f"{symbol}_{timeframe}.parquet"


def has_order_flow(df: pd.DataFrame) -> bool:
    """True if this dataset carries signed volume (i.e. it was built from ticks)."""
    return all(column in df.columns for column in ORDER_FLOW_COLUMNS)


def load_raw(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load one symbol/timeframe Parquet as raw UTC-indexed bars.

    Always OHLCV; additionally the order-flow columns when the dataset has them.
    """
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
    keep = EXPECTED_COLUMNS + [c for c in ORDER_FLOW_COLUMNS if c in df.columns]
    df = df[keep]

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
