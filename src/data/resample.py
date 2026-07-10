"""Rebuild bars from ticks - including the order flow a bar file can never carry.

One job: stream the stitched tick file once, fold it into base bars, and derive
every higher timeframe from those. Each bar carries OHLCV *and* signed volume:
``delta``, ``buy_volume``, ``sell_volume``, ``trades``.

Why this is the only way to get delta: a bar records total volume, not which
side was the aggressor. That information is destroyed by aggregation and no
transformation recovers it. Measured on this data, ~18% of bars close in the
opposite direction to their net order flow, and the candle explains only 56% of
delta. Essentially every tick prints at the bid or the ask - only 1,527 contracts
of 321,879,452 (0.000474%) land strictly between - so the aggressor is
unambiguous here, and only here.

Two things this code is careful about, both learned the hard way:

**Timestamps are not unique.** 52% of ticks share a timestamp with a neighbour.
Selecting a bucket's close with ``idxmax`` on time returns the *first* row of a
tie, not the last, and silently corrupts the close. Bucket aggregation uses
``.first()`` / ``.last()``, which respect file order, and cross-chunk merges
break ties by chunk order.

**Buckets straddle chunk boundaries.** A chunk ends mid-bar, so partial buckets
are carried and combined at the end rather than emitted as if complete.

Prices are BACK-ADJUSTED. The tick file stores the raw traded price per contract
plus a per-segment offset ``adj``; glued end to end the raw prices jump 211-270
points at each quarterly roll, which a strategy would read as a huge move. We
subtract ``adj`` and re-anchor so the NEWEST contract carries its real prices -
historical levels shift, current ones do not. Order flow is untouched: ``adj`` is
a constant within a segment, so bid/ask comparison (and therefore the aggressor)
is unaffected.

Bars are CLOSE-stamped to match the NT8 store: a bar labelled T covers
``(T - step, T]``, i.e. ``closed='right', label='right'``.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.config import ticks as cfg

logger = logging.getLogger(__name__)

_READ_COLUMNS = ["ts", "price", "bid", "ask", "volume", "adj"]


def classify(price, bid, ask) -> np.ndarray:
    """Aggressor side per trade: +1 lifted the offer, -1 hit the bid, 0 unknown.

    A trade printing at or above the ask was a buyer crossing the spread; at or
    below the bid, a seller. Mid-spread prints are vanishingly rare on this data
    (0.000474% of volume) but they DO occur, and a 0 contributes to neither side.
    Never guess one into a side: a fabricated aggressor is worse than a missing
    one, because the backtest would trust it. This is why buy_volume +
    sell_volume can fall short of volume on some bars.

    How MANY bars is a property of the bar, not of the tape: a longer bar has more
    chances to contain one of those prints. Measured on NQT: 0.024% of 15s bars,
    0.045% of 30s, 0.086% of 1m, 0.387% of 5m, 1.08% of 15m, 3.88% of 60m - and
    the worst single bar is short by 120 contracts, not by one or two. The share
    of CONTRACTS (0.000474%) is the invariant; the share of bars is not, and
    quoting one figure for it is quoting a timeframe without naming it.
    """
    return np.where(price >= ask, 1, np.where(price <= bid, -1, 0)).astype(np.int8)


def anchor_offset() -> float:
    """``adj`` of the newest segment, so re-anchoring leaves current prices real.

    ``adj`` is cumulative across rolls and never decreases, so its maximum is in
    the last row group. Reading one group beats scanning 296M values.
    """
    reader = pq.ParquetFile(cfg.TICK_FILE)
    last = reader.read_row_group(reader.metadata.num_row_groups - 1, columns=["adj"])
    return float(last.column("adj").to_pandas().max())


def _fold_chunk(df: pd.DataFrame, freq: str, chunk_index: int, anchor: float) -> pd.DataFrame:
    """Fold one chunk of ticks into (possibly partial) bars for its buckets."""
    raw = df["price"].to_numpy()
    # Aggressor is decided on RAW quotes: adj is constant within a segment, so it
    # cancels in the comparison and applying it first would only lose precision.
    side = classify(raw, df["bid"].to_numpy(), df["ask"].to_numpy())
    volume = df["volume"].to_numpy()

    # Continuous, newest contract anchored at its real prices.
    price = raw - df["adj"].to_numpy() + anchor

    work = pd.DataFrame({
        "ts": df["ts"].to_numpy(),
        "price": price,
        "volume": volume,
        "signed": side * volume,
        "buy": np.where(side > 0, volume, 0),
        "sell": np.where(side < 0, volume, 0),
    })
    # Close-stamped: a tick at exactly T belongs to the bar labelled T.
    work["label"] = work["ts"].dt.ceil(freq)

    grouped = work.groupby("label", sort=True)
    bars = pd.DataFrame({
        "first_ts": grouped["ts"].min(),
        "last_ts": grouped["ts"].max(),
        # .first()/.last() take the first/last ROW of the group, which is what
        # file order means. Never idxmin/idxmax on ts - 52% of ts values tie.
        "open": grouped["price"].first(),
        "close": grouped["price"].last(),
        "high": grouped["price"].max(),
        "low": grouped["price"].min(),
        "volume": grouped["volume"].sum(),
        "delta": grouped["signed"].sum(),
        "buy_volume": grouped["buy"].sum(),
        "sell_volume": grouped["sell"].sum(),
        "trades": grouped["price"].count(),
    })
    bars["chunk"] = chunk_index
    return bars.reset_index()


def _combine(partials: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge partial buckets that were split across chunk boundaries.

    Chunks arrive in time order, so within a label the lowest chunk index holds
    the true open and the highest holds the true close. That also resolves ties
    at a boundary, where two chunks can share the same timestamp.
    """
    frame = pd.concat(partials, ignore_index=True)
    frame = frame.sort_values(["label", "chunk"], kind="stable")
    grouped = frame.groupby("label", sort=True)

    bars = pd.DataFrame({
        "open": grouped["open"].first(),
        "high": grouped["high"].max(),
        "low": grouped["low"].min(),
        "close": grouped["close"].last(),
        "volume": grouped["volume"].sum(),
        "delta": grouped["delta"].sum(),
        "buy_volume": grouped["buy_volume"].sum(),
        "sell_volume": grouped["sell_volume"].sum(),
        "trades": grouped["trades"].sum(),
    })
    bars.index.name = "ts"
    return bars


def base_bars(progress=None) -> pd.DataFrame:
    """Stream the whole tick file into ``cfg.BASE_TIMEFRAME`` bars."""
    reader = pq.ParquetFile(cfg.TICK_FILE)
    freq = cfg.FREQ[cfg.BASE_TIMEFRAME]
    groups = reader.metadata.num_row_groups
    logger.info("Resampling %s (%s ticks, %d row groups) -> %s bars",
                cfg.TICK_FILE.name, f"{reader.metadata.num_rows:,}", groups,
                cfg.BASE_TIMEFRAME)

    anchor = anchor_offset()
    logger.info("Back-adjust anchor: %+.2f (newest contract keeps real prices)", anchor)

    partials: list[pd.DataFrame] = []
    seen = 0
    for chunk_index, start in enumerate(range(0, groups, cfg.ROW_GROUPS_PER_CHUNK)):
        stop = min(start + cfg.ROW_GROUPS_PER_CHUNK, groups)
        table = reader.read_row_groups(list(range(start, stop)), columns=_READ_COLUMNS)
        df = table.to_pandas()
        partials.append(_fold_chunk(df, freq, chunk_index, anchor))
        seen += len(df)
        if progress is not None:
            progress(seen, reader.metadata.num_rows)

    bars = _combine(partials)
    # Ticks are UTC (proven: the only empty hour is the 21:00-22:00 CME halt).
    bars.index = bars.index.tz_localize("UTC")
    logger.info("Base bars: %s rows, %s -> %s",
                f"{len(bars):,}", bars.index[0], bars.index[-1])
    return bars


def derive(base: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Fold base bars up into a coarser timeframe. Exact: 15s divides them all."""
    grouped = base.resample(cfg.FREQ[timeframe], closed="right", label="right")
    bars = pd.DataFrame({
        "open": grouped["open"].first(),
        "high": grouped["high"].max(),
        "low": grouped["low"].min(),
        "close": grouped["close"].last(),
        "volume": grouped["volume"].sum(),
        "delta": grouped["delta"].sum(),
        "buy_volume": grouped["buy_volume"].sum(),
        "sell_volume": grouped["sell_volume"].sum(),
        "trades": grouped["trades"].sum(),
    })
    # Empty buckets are halts, weekends and holidays - not bars. Drop them
    # rather than emit a phantom candle with no trades in it.
    return bars.dropna(subset=["open"])
