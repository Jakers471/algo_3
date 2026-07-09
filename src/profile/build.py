"""Fold the tick file into volume at price, once, into a packed store.

One job: stream every tick, bin its volume by exact price level and by the base
bar it landed in, and write two files the chart can memmap:

    vap.bin     one 12-byte record per (bar, price level): tick, volume, buy
    vap_idx.bin one 16-byte record per bar: close time, offset, count

Why this file exists at all. A bar records total volume, its high and its low -
never where inside that range the contracts changed hands. Spreading a bar's
volume across its range would be a fabrication, and the profile drawn from it
would be a picture of the assumption rather than of the market. Only the ticks
know, so only the ticks are asked.

**Bins are one tick wide, exactly.** After back-adjustment 100.00% of prices land
on the 0.25 grid, so a price becomes an integer (``round(price * 4)``) with no
rounding error, and any coarser binning downstream is an exact fold of this one.

Two things inherited from resample.py, for the same hard-won reasons. Prices are
back-adjusted and re-anchored so the newest contract keeps its real levels. And a
bar straddles a chunk boundary, so the last (incomplete) bar of every chunk is
carried forward rather than written as though it were finished.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.config import profile as cfg
from src.config import ticks as ticks_cfg
from src.data.resample import anchor_offset, classify

logger = logging.getLogger(__name__)

_READ_COLUMNS = ["ts", "price", "bid", "ask", "volume", "adj"]

# One row per (bar, price level).
VAP_DTYPE = np.dtype([("tick", "<i4"), ("volume", "<u4"), ("buy", "<u4")])
# One row per bar: where its levels start, and how many there are.
IDX_DTYPE = np.dtype([("time", "<u4"), ("offset", "<u8"), ("count", "<u4")])


def paths(symbol: str, timeframe: str) -> tuple:
    base = cfg.CACHE_DIR / f"{symbol}_{timeframe}"
    return base.with_suffix(".vap"), base.with_suffix(".idx")


def _levels(df: pd.DataFrame, freq: str, anchor: float) -> pd.DataFrame:
    """One chunk of ticks -> (bar, price level) volumes, sorted."""
    raw = df["price"].to_numpy()
    # Aggressor on RAW quotes: adj is constant within a segment, so it cancels.
    side = classify(raw, df["bid"].to_numpy(), df["ask"].to_numpy())
    volume = df["volume"].to_numpy()

    price = raw - df["adj"].to_numpy() + anchor
    tick = np.rint(price / cfg.TICK_SIZE).astype(np.int64)

    work = pd.DataFrame({
        # Close-stamped: a tick at exactly T belongs to the bar labelled T.
        "label": df["ts"].dt.ceil(freq),
        "tick": tick,
        "volume": volume,
        "buy": np.where(side > 0, volume, 0),
    })
    out = work.groupby(["label", "tick"], sort=True).sum().reset_index()
    return out


def build(symbol: str = None, timeframe: str = None, progress=None) -> dict:
    """Stream the tick file into the packed volume-at-price store."""
    symbol = symbol or ticks_cfg.OUTPUT_SYMBOL
    timeframe = timeframe or ticks_cfg.BASE_TIMEFRAME
    freq = ticks_cfg.FREQ[timeframe]

    reader = pq.ParquetFile(ticks_cfg.TICK_FILE)
    groups = reader.metadata.num_row_groups
    anchor = anchor_offset()
    logger.info("Volume at price: %s ticks -> %s %s levels (anchor %+.2f)",
                f"{reader.metadata.num_rows:,}", symbol, timeframe, anchor)

    vap_path, idx_path = paths(symbol, timeframe)
    vap_path.parent.mkdir(parents=True, exist_ok=True)

    carry: pd.DataFrame | None = None
    offset = 0
    bars = 0
    seen = 0

    with open(vap_path, "wb") as vap_file, open(idx_path, "wb") as idx_file:
        for start in range(0, groups, ticks_cfg.ROW_GROUPS_PER_CHUNK):
            stop = min(start + ticks_cfg.ROW_GROUPS_PER_CHUNK, groups)
            df = reader.read_row_groups(list(range(start, stop)), columns=_READ_COLUMNS).to_pandas()
            seen += len(df)

            levels = _levels(df, freq, anchor)
            if carry is not None:
                levels = (pd.concat([carry, levels], ignore_index=True)
                          .groupby(["label", "tick"], sort=True).sum().reset_index())

            # The final bar of a chunk may continue into the next one. Everything
            # before it is complete and can be written; that one is carried.
            last_label = levels["label"].iloc[-1]
            complete = levels[levels["label"] != last_label]
            carry = levels[levels["label"] == last_label]

            offset, bars = _write(vap_file, idx_file, complete, offset, bars)
            if progress is not None:
                progress(seen, reader.metadata.num_rows)

        if carry is not None and len(carry):
            offset, bars = _write(vap_file, idx_file, carry, offset, bars)

    logger.info("Wrote %s levels across %s bars -> %s",
                f"{offset:,}", f"{bars:,}", vap_path.name)
    return {"levels": offset, "bars": bars, "vap": vap_path, "index": idx_path}


def _write(vap_file, idx_file, levels: pd.DataFrame, offset: int, bars: int) -> tuple:
    """Append one run of complete bars, and the index rows that locate them."""
    if not len(levels):
        return offset, bars

    rows = np.empty(len(levels), dtype=VAP_DTYPE)
    rows["tick"] = levels["tick"].to_numpy()
    rows["volume"] = levels["volume"].to_numpy()
    rows["buy"] = levels["buy"].to_numpy()
    vap_file.write(rows.tobytes())

    # Bars are already grouped and time-sorted; count the levels in each.
    labels = levels["label"].to_numpy()
    edges = np.flatnonzero(np.r_[True, labels[1:] != labels[:-1]])
    counts = np.diff(np.r_[edges, len(labels)])

    index = np.empty(len(edges), dtype=IDX_DTYPE)
    index["time"] = (levels["label"].iloc[edges].astype("int64") // 10**9).to_numpy()
    index["offset"] = offset + edges
    index["count"] = counts
    idx_file.write(index.tobytes())

    return offset + len(levels), bars + len(edges)
