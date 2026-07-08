"""Consolidation bases: the tradeable value-area boxes a breakout enters.

One job: from a per-bar CONSOLIDATION mask, find the runs (>= min_len bars),
grade each once for its value area (VAH/VAL), and expose per bar the most recent
COMPLETED base that is still fresh (ended <= max_age bars ago). Look-ahead-safe:
a base graded from a run ending at b is only offered from bar b+1 onward. Pure.
"""

from __future__ import annotations

import numpy as np

from src.indicators.grade import grade


def _runs(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    """Contiguous True runs of length >= min_len, as (start, end) inclusive."""
    out: list[tuple[int, int]] = []
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i >= min_len:
                out.append((i, j - 1))
            i = j
        else:
            i += 1
    return out


def current_base(bars, is_cons: np.ndarray, min_len: int = 15, max_age: int = 40,
                 n_rows: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar (vah, val) of the current tradeable base, NaN where none.

    A run ending at bar b yields a fixed base (graded once); it is offered to bars
    b+1 .. b+max_age. A later run overrides an earlier one.
    """
    n = len(bars)
    vah = np.full(n, np.nan)
    val = np.full(n, np.nan)

    graded = []  # (end_index, vah, val), sorted by end
    for a, b in _runs(is_cons, min_len):
        g = grade(bars.iloc[a:b + 1], n_rows=n_rows)
        if g.vah > g.val:
            graded.append((b, g.vah, g.val))

    ri, cur = 0, None
    for i in range(n):
        while ri < len(graded) and graded[ri][0] < i:  # base ended strictly before bar i
            cur = graded[ri]
            ri += 1
        if cur is not None and (i - cur[0]) <= max_age:
            vah[i], val[i] = cur[1], cur[2]
    return vah, val
