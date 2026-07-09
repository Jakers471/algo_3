"""Pack a Parquet bar file into a memmap-ready binary the chart can slice.

One job: turn ``data/<SYM>/<SYM>_<TF>.parquet`` into three files under the
chart cache - a fixed-width bar record array (the exact bytes sent on the
wire), a contiguous timestamp column (so locating a date is a binary search
that touches a handful of pages), and a JSON sidecar describing both.

Why a second copy of data we already have: Parquet is columnar and compressed,
so answering "give me bars 412,000..413,500" means decompressing row groups.
The packed form is a flat C array of 24-byte records - slicing it is pointer
arithmetic over the OS page cache, and the slice IS the wire payload. Building
is a one-time cost per symbol/timeframe; reading is near-instant forever after.

Plumbing only: it reads via data.loader and writes bytes. Serving is store.py.
"""

from __future__ import annotations

import json
import logging

import numpy as np

from src.config import chart as chart_cfg
from src.data import loader

logger = logging.getLogger(__name__)

# One bar = 24 bytes. Little-endian, fixed width, no padding.
#   time   uint32  - epoch seconds UTC (valid to 2106)
#   ohlc   float32 - exact for quarter-tick futures prices (< 2^24 quarter-ticks)
#   volume float32 - exact to 16.7M contracts per bar
BAR_DTYPE = np.dtype([
    ("time", "<u4"),
    ("open", "<f4"),
    ("high", "<f4"),
    ("low", "<f4"),
    ("close", "<f4"),
    ("volume", "<f4"),
])
TIME_DTYPE = np.dtype("<u4")

# Bump when BAR_DTYPE or the file layout changes, to invalidate stale caches.
FORMAT_VERSION = 1


def paths_for(symbol: str, timeframe: str) -> tuple:
    """The (bars, times, meta) cache paths for a symbol/timeframe (no I/O)."""
    stem = chart_cfg.CACHE_DIR / f"{symbol}_{timeframe}"
    return (
        stem.with_suffix(".bars.bin"),
        stem.with_suffix(".times.bin"),
        stem.with_suffix(".meta.json"),
    )


def is_packed(symbol: str, timeframe: str) -> bool:
    """True if a current-format cache exists for this symbol/timeframe."""
    bars_fp, times_fp, meta_fp = paths_for(symbol, timeframe)
    if not (bars_fp.exists() and times_fp.exists() and meta_fp.exists()):
        return False
    try:
        meta = json.loads(meta_fp.read_text())
    except (OSError, ValueError):
        return False
    return meta.get("format_version") == FORMAT_VERSION


def pack(symbol: str, timeframe: str, *, force: bool = False) -> dict:
    """Build the packed cache for one symbol/timeframe; return its meta.

    Idempotent: a present, current-format cache is left alone unless ``force``.
    Packs the FULL history (loader.load_raw, not the backtest window) - the
    chart is for looking at any period, including pre-backtest bars whose
    absolute levels are synthetic from back-adjustment.
    """
    bars_fp, times_fp, meta_fp = paths_for(symbol, timeframe)
    if not force and is_packed(symbol, timeframe):
        logger.debug("Chart cache hit: %s %s", symbol, timeframe)
        return json.loads(meta_fp.read_text())

    logger.info("Packing %s %s -> chart cache (one-time)", symbol, timeframe)
    df = loader.load_raw(symbol, timeframe)

    recs = np.empty(len(df), dtype=BAR_DTYPE)
    # .view("int64") on a UTC DatetimeIndex gives nanoseconds since epoch.
    recs["time"] = (df.index.values.astype("datetime64[s]").astype("int64")).astype("<u4")
    for col in ("open", "high", "low", "close", "volume"):
        recs[col] = df[col].to_numpy(dtype="<f4")

    chart_cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    recs.tofile(bars_fp)
    recs["time"].astype(TIME_DTYPE).tofile(times_fp)

    meta = {
        "format_version": FORMAT_VERSION,
        "symbol": symbol,
        "timeframe": timeframe,
        "count": int(len(recs)),
        "bar_bytes": BAR_DTYPE.itemsize,
        "first_time": int(recs["time"][0]) if len(recs) else None,
        "last_time": int(recs["time"][-1]) if len(recs) else None,
    }
    meta_fp.write_text(json.dumps(meta, indent=2))
    logger.info("Packed %s %s: %d bars, %.1f MB",
                symbol, timeframe, len(recs), bars_fp.stat().st_size / 1e6)
    return meta


def pack_all(*, force: bool = False) -> list[dict]:
    """Pack every symbol/timeframe whose Parquet exists. Returns their metas."""
    metas = []
    for symbol in chart_cfg.SYMBOLS:
        for timeframe in chart_cfg.TIMEFRAMES:
            if not loader.path_for(symbol, timeframe).exists():
                continue
            metas.append(pack(symbol, timeframe, force=force))
    return metas
