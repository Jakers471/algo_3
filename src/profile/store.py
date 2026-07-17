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
        # Two traps, both of which turn a binary search into a full scan of 1.6M
        # rows - 10 ms per lookup, one lookup per bar, and a 5,000-bar overlay
        # request that never finishes.
        #
        # `index["time"]` is a strided view into 16-byte records, so numpy copies
        # it out of the memmap every time. And it is uint32: searching it with a
        # Python int promotes the WHOLE ARRAY to int64 first. Materialise the
        # columns once, contiguous and already int64, and the search costs
        # microseconds again.
        columns = (np.ascontiguousarray(index["time"], dtype=np.int64),
                   np.ascontiguousarray(index["offset"], dtype=np.int64),
                   np.ascontiguousarray(index["count"], dtype=np.int64))
        _CACHE[key] = (levels, columns)
    return _CACHE[key]


def bar_count(symbol: str, timeframe: str) -> int:
    return len(_open(symbol, timeframe)[1][0])


def histogram(symbol: str, timeframe: str, start: int, end: int) -> tuple:
    """Volume at each price traded in ``(start, end]``, in epoch seconds.

    Returns ``(prices, volume, buy_volume)``, prices ascending. Bars are
    close-stamped, so a bar labelled exactly ``start`` belongs to the range
    before it and is excluded; one labelled ``end`` is included.
    """
    levels, (times, offsets, counts) = _open(symbol, timeframe)

    first = int(np.searchsorted(times, start, side="right"))
    last = int(np.searchsorted(times, end, side="right"))
    if last <= first:
        return np.empty(0), np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    lo = int(offsets[first])
    hi = int(offsets[last - 1] + counts[last - 1])
    span = levels[lo:hi]

    # One bar's levels are unique, but a range spans many bars and a price
    # trades in several of them. Fold the duplicates. bincount, not add.at -
    # the unbuffered ufunc is an order of magnitude slower for no benefit here.
    ticks, inverse = np.unique(span["tick"], return_inverse=True)
    volume = np.bincount(inverse, weights=span["volume"], minlength=len(ticks))
    buy = np.bincount(inverse, weights=span["buy"], minlength=len(ticks))

    return ticks * cfg.TICK_SIZE, volume.astype(np.int64), buy.astype(np.int64)


class Ladder:
    """A running histogram on the tick grid: dense, and sorted by construction.

    The live accumulator behind every developing volume profile - `indicators/
    profile.py`'s swing-to-swing range and `indicators/session_stats.py`'s
    session range both fold their bars into one of these; only the reset policy
    differs. One accumulator, so a bug in the fold is fixed once.

    Prices land exactly on the tick grid, so a price is an integer index and a
    bar folds in with one vectorised add. A dict of prices would need sorting
    into arrays on every bar, and over a 5,000-bar window that sort dominated
    everything else the chart did.
    """

    SLAB = 512      # grow in slabs; padding by one bar's width reallocates always

    def __init__(self) -> None:
        self._lo: int | None = None            # tick index of self._volume[0]
        self._volume = np.zeros(0, np.int64)
        self._buy = np.zeros(0, np.int64)

    def __bool__(self) -> bool:
        return self._lo is not None

    def add(self, prices, volume, buy) -> None:
        if len(prices) == 0:
            return          # nothing traded: there is no price to attribute it to
        ticks = np.rint(prices / cfg.TICK_SIZE).astype(np.int64)
        lo, hi = int(ticks[0]), int(ticks[-1])          # vap prices are ascending
        if self._lo is None:
            self._lo = lo - self.SLAB
            self._volume = np.zeros(hi - lo + 1 + 2 * self.SLAB, np.int64)
            self._buy = np.zeros_like(self._volume)
        else:
            self._grow(lo, hi)
        idx = ticks - self._lo
        # A bar's levels are already unique - the store folds them - so a plain
        # fancy-index add is correct, and np.add.at's unbuffered path is paid for
        # nothing.
        self._volume[idx] += volume
        self._buy[idx] += buy

    def _grow(self, lo: int, hi: int) -> None:
        left = self._lo - lo
        right = hi - (self._lo + len(self._volume) - 1)
        if left <= 0 and right <= 0:
            return
        left = max(left, 0) + (self.SLAB if left > 0 else 0)
        right = max(right, 0) + (self.SLAB if right > 0 else 0)
        self._volume = np.pad(self._volume, (left, right))
        self._buy = np.pad(self._buy, (left, right))
        self._lo -= left

    def arrays(self) -> tuple:
        """Ascending prices and their volumes. Empty levels are dropped."""
        filled = np.flatnonzero(self._volume)
        prices = (self._lo + filled) * cfg.TICK_SIZE
        return prices, self._volume[filled], self._buy[filled]


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

    # Bin indices are a contiguous integer range, so bincount folds them in one
    # pass. np.unique sorts, which over a 5,000-bar walk cost seconds per
    # request for an answer the ordering was already going to give.
    edges = np.floor(prices / bin_size).astype(np.int64)
    base = edges[0]
    inverse = edges - base
    size = int(inverse[-1]) + 1
    v = np.bincount(inverse, weights=volume, minlength=size).astype(np.int64)
    b = np.bincount(inverse, weights=buy, minlength=size).astype(np.int64)

    filled = np.flatnonzero(v)
    # Name a bin by its lower edge; the price you can trade is the level, not
    # the middle of an interval nobody quotes.
    return (base + filled) * bin_size, v[filled], b[filled]
