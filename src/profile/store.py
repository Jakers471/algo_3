"""Read the packed volume-at-price store: slice a time range, get a histogram.

One job: memmap the two files ``build.py`` wrote and answer one question -
"how much volume traded at each price between t0 and t1?"

The index is one row per base bar, ascending in time, so locating a range is a
binary search rather than a scan. The levels of a bar sit contiguously, so a range
of bars is one contiguous slice of the level file. Nothing is decompressed, and
nothing is read that the answer does not need.

Aggregation is a fold, never a re-bin. Levels are stored one tick wide - the
finest the market resolves - so summing them into a coarser bin is exact. Going
the other way is impossible, which is why the store is built at one tick.
"""

from __future__ import annotations

import logging

import numpy as np

from src.config import profile as cfg
from src.profile.build import IDX_DTYPE, VAP_DTYPE, paths

logger = logging.getLogger(__name__)

_CACHE: dict[tuple, tuple] = {}


class NotBuilt(FileNotFoundError):
    """The volume-at-price store has not been built. Run: python -m src.cli.vap"""


def _open(symbol: str, timeframe: str) -> tuple:
    key = (symbol, timeframe)
    if key not in _CACHE:
        vap_path, idx_path = paths(symbol, timeframe)
        if not vap_path.exists() or not idx_path.exists():
            raise NotBuilt(
                f"no volume-at-price store for {symbol} {timeframe}; "
                f"run: python -m src.cli.vap")
        levels = np.memmap(vap_path, dtype=VAP_DTYPE, mode="r")
        index = np.memmap(idx_path, dtype=IDX_DTYPE, mode="r")
        _CACHE[key] = (levels, index)
    return _CACHE[key]


def bar_count(symbol: str, timeframe: str) -> int:
    return len(_open(symbol, timeframe)[1])


def histogram(symbol: str, timeframe: str, start: int, end: int) -> tuple:
    """Volume at each price traded in ``(start, end]``, in epoch seconds.

    Returns ``(prices, volume, buy_volume)``, prices ascending. Bars are
    close-stamped, so a bar labelled exactly ``start`` belongs to the range
    before it and is excluded; one labelled ``end`` is included.
    """
    levels, index = _open(symbol, timeframe)
    times = index["time"]

    first = int(np.searchsorted(times, start, side="right"))
    last = int(np.searchsorted(times, end, side="right"))
    if last <= first:
        return np.empty(0), np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    lo = int(index["offset"][first])
    hi = int(index["offset"][last - 1] + index["count"][last - 1])
    span = levels[lo:hi]

    # One bar's levels are unique, but a range spans many bars and a price
    # trades in several of them. Fold the duplicates.
    ticks, inverse = np.unique(span["tick"], return_inverse=True)
    volume = np.zeros(len(ticks), dtype=np.int64)
    buy = np.zeros(len(ticks), dtype=np.int64)
    np.add.at(volume, inverse, span["volume"])
    np.add.at(buy, inverse, span["buy"])

    return ticks * cfg.TICK_SIZE, volume, buy


def rebin(prices: np.ndarray, volume: np.ndarray, buy: np.ndarray,
          bin_size: float) -> tuple:
    """Fold one-tick levels into wider bins. Exact - never a re-slice of a bar.

    ``bin_size`` should be derived from ``range_scale``, not fixed in points: a
    profile binned in ticks has four times as many bins at the New York open as
    it does overnight, and the same market then looks spiky in one hour and
    smooth in another.
    """
    if len(prices) == 0 or bin_size <= cfg.TICK_SIZE:
        return prices, volume, buy

    edges = np.floor(prices / bin_size).astype(np.int64)
    keys, inverse = np.unique(edges, return_inverse=True)
    v = np.zeros(len(keys), dtype=np.int64)
    b = np.zeros(len(keys), dtype=np.int64)
    np.add.at(v, inverse, volume)
    np.add.at(b, inverse, buy)
    # Name a bin by its lower edge; the price you can trade is the level, not
    # the middle of an interval nobody quotes.
    return keys * bin_size, v, b
