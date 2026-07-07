"""Volume-profile core math: volume-per-price-row and the value area.

Pure, reusable primitives for anything that needs a POC / value area (the GRADE
engine, a session profile, a chart). Overlap-weighted: a bar spanning several
rows contributes to each in proportion to how much of the bar's range overlaps
that row (a zero-range bar dumps its volume into the single row at its price).
"""

from __future__ import annotations

import numpy as np


def profile_for(highs, lows, vols, base: float, row_size: float, n_rows: int) -> np.ndarray:
    """Overlap-weighted volume per row on a grid whose row i spans
    ``[base + i*row_size, base + (i+1)*row_size)``. Returns ``ndarray[n_rows]``."""
    binvol = np.zeros(n_rows)
    for p in range(len(highs)):
        bl, bh, v = lows[p], highs[p], vols[p]
        if bh <= bl:  # zero-range bar -> the single row containing its price
            idx = min(max(int((bl - base) / row_size), 0), n_rows - 1)
            binvol[idx] += v
            continue
        lo_i = min(max(int((bl - base) / row_size), 0), n_rows - 1)
        hi_i = min(max(int((bh - base) / row_size), 0), n_rows - 1)
        span = bh - bl
        for bi in range(lo_i, hi_i + 1):
            b_bot = base + bi * row_size
            b_top = b_bot + row_size
            overlap = min(bh, b_top) - max(bl, b_bot)
            if overlap > 0:
                binvol[bi] += v * (overlap / span)
    return binvol


def value_area(vol: np.ndarray, poc_idx: int, pct: float) -> tuple[int, int]:
    """Indices ``(lo, hi)`` of the value-area block: expand out from the POC row,
    each step taking the heavier neighbor, until the block holds >= ``pct`` of
    total volume."""
    target = vol.sum() * pct
    lo = hi = poc_idx
    acc = float(vol[poc_idx])
    n = len(vol)
    while acc < target and (lo > 0 or hi < n - 1):
        below = vol[lo - 1] if lo > 0 else -1.0
        above = vol[hi + 1] if hi < n - 1 else -1.0
        if above >= below:
            hi += 1
            acc += float(vol[hi])
        else:
            lo -= 1
            acc += float(vol[lo])
    return lo, hi
