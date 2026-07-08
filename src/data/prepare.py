"""Turn raw bars into clean, session-aware bars for strategy/backtest.

One job: apply the data-truth rules the audit dictates - restrict to the
backtest window, mark session gaps so no engine computes a return across one,
and apply the zero-volume policy. Pure logic over a DataFrame; the file I/O
lives in loader.py.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.config import backtest as bt_cfg
from src.data import loader

logger = logging.getLogger(__name__)


def get_bars(symbol: str, timeframe: str, *, window: bool = True) -> pd.DataFrame:
    """Load and prepare bars: raw -> windowed -> gap-marked -> vol policy.

    Set ``window=False`` to keep the full history (pre-BACKTEST_START), knowing
    old absolute levels are synthetic from back-adjustment (audit: back_adjustment).
    """
    df = loader.load_raw(symbol, timeframe)
    if window:
        df = filter_window(df)
    df = mark_gaps(df, timeframe)
    df = apply_zero_volume(df)
    logger.info(
        "Prepared %s %s: %d bars (%d session gaps)",
        symbol, timeframe, len(df), int(df["gap_before"].sum()),
    )
    return df


def filter_window(df: pd.DataFrame) -> pd.DataFrame:
    """Restrict to [BACKTEST_START, DATA_END] (audit: back_adjustment / stale_data)."""
    start = pd.Timestamp(bt_cfg.BACKTEST_START, tz="UTC")
    out = df[df.index >= start]
    if bt_cfg.DATA_END:
        out = out[out.index <= pd.Timestamp(bt_cfg.DATA_END)]
    return out


def mark_gaps(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Flag bars whose gap to the prior bar exceeds one timeframe step.

    A True in ``gap_before`` marks a session boundary (overnight halt, weekend,
    holiday). Engines must treat it as a break - never a tradeable move
    (audit: gap_awareness, required).
    """
    step = pd.Timedelta(loader.TIMEFRAMES[timeframe])
    df = df.copy()
    df["gap_before"] = df.index.to_series().diff() > step
    return df


def apply_zero_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Honor the zero-volume policy (audit: zero_volume_bars, info)."""
    if bt_cfg.SKIP_ZERO_VOLUME_BARS:
        before = len(df)
        df = df[df["volume"] > 0]
        logger.debug("Dropped %d zero-volume bars", before - len(df))
    return df
