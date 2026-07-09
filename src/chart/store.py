"""Read bars out of the packed chart cache, fast.

One job: answer the two questions the chart asks - "give me bars [start, start+n)"
and "which bar index is this timestamp?" - without ever parsing Parquet.

Both are served off ``np.memmap``, so the process never loads a dataset into
RAM: the OS pages in only the bytes touched, and a slice of the bar file is
already the exact wire payload (no serialization step). Locating a timestamp is
a binary search over the contiguous time column, touching ~log2(n) pages.

Pure data access. It does not know about HTTP; that is api.py and server.py.
"""

from __future__ import annotations

import json
import logging

import numpy as np

from src.chart import packer

logger = logging.getLogger(__name__)

# symbol/timeframe -> open memmaps. Held open for the process lifetime; a memmap
# costs address space, not resident memory.
_BARS: dict[tuple[str, str], np.memmap] = {}
_TIMES: dict[tuple[str, str], np.memmap] = {}
_META: dict[tuple[str, str], dict] = {}


class NotPacked(LookupError):
    """Raised when a symbol/timeframe has no packed cache to read."""


def _key(symbol: str, timeframe: str) -> tuple[str, str]:
    return (symbol.upper(), timeframe.lower())


def meta(symbol: str, timeframe: str) -> dict:
    """The sidecar meta for a symbol/timeframe (count, first/last time)."""
    k = _key(symbol, timeframe)
    if k not in _META:
        _, _, meta_fp = packer.paths_for(*k)
        if not meta_fp.exists():
            raise NotPacked(f"No packed chart cache for {k[0]} {k[1]}")
        _META[k] = json.loads(meta_fp.read_text())
    return _META[k]


def _bars_mm(symbol: str, timeframe: str) -> np.memmap:
    k = _key(symbol, timeframe)
    if k not in _BARS:
        bars_fp, _, _ = packer.paths_for(*k)
        if not bars_fp.exists():
            raise NotPacked(f"No packed chart cache for {k[0]} {k[1]}")
        _BARS[k] = np.memmap(bars_fp, dtype=packer.BAR_DTYPE, mode="r")
        logger.debug("Memmapped %s (%d bars)", bars_fp.name, len(_BARS[k]))
    return _BARS[k]


def _times_mm(symbol: str, timeframe: str) -> np.memmap:
    k = _key(symbol, timeframe)
    if k not in _TIMES:
        _, times_fp, _ = packer.paths_for(*k)
        if not times_fp.exists():
            raise NotPacked(f"No packed chart cache for {k[0]} {k[1]}")
        _TIMES[k] = np.memmap(times_fp, dtype=packer.TIME_DTYPE, mode="r")
    return _TIMES[k]


def count(symbol: str, timeframe: str) -> int:
    """How many bars this symbol/timeframe holds."""
    return int(meta(symbol, timeframe)["count"])


def slice_bytes(symbol: str, timeframe: str, start: int, n: int) -> tuple[bytes, int]:
    """Bars ``[start, start+n)`` as raw wire bytes, plus the clamped start index.

    Out-of-range requests clamp rather than raise - the client walks off the end
    of the data at the right edge of a replay, and an empty payload is the honest
    answer, not an error.
    """
    mm = _bars_mm(symbol, timeframe)
    total = len(mm)
    start = max(0, min(int(start), total))
    stop = max(start, min(start + int(n), total))
    return mm[start:stop].tobytes(), start


def locate(symbol: str, timeframe: str, epoch_seconds: int) -> int:
    """Index of the first bar at or after ``epoch_seconds`` (binary search).

    Clamped to a valid index, so a timestamp before the data starts snaps to the
    first bar and one after the end snaps to the last.
    """
    times = _times_mm(symbol, timeframe)
    if len(times) == 0:
        raise NotPacked(f"Packed cache for {symbol} {timeframe} is empty")
    idx = int(np.searchsorted(times, np.uint32(max(0, epoch_seconds)), side="left"))
    return max(0, min(idx, len(times) - 1))


def datasets() -> dict:
    """Every packed symbol/timeframe with its bar count and time span.

    Shape: ``{"NQ": {"5m": {count, first_time, last_time}, ...}, ...}``
    """
    from src.config import chart as chart_cfg

    out: dict[str, dict] = {}
    for symbol in chart_cfg.SYMBOLS:
        for timeframe in chart_cfg.TIMEFRAMES:
            if not packer.is_packed(symbol, timeframe):
                continue
            m = meta(symbol, timeframe)
            out.setdefault(symbol, {})[timeframe] = {
                "count": m["count"],
                "first_time": m["first_time"],
                "last_time": m["last_time"],
            }
    return out
