"""Point of control and the value area, from a histogram of volume at price.

One job, pure: given the volume traded at each price level, say where most of it
changed hands (the POC) and the contiguous band around it holding ``VALUE_AREA``
of the total (VAL up to VAH).

**The band must be contiguous.** Taking the highest-volume levels until 70% is
covered would give a set of prices with holes in it, which is not a value area -
it is a list. The convention is to start at the point of control and grow
outwards, each step taking whichever side offers more volume, until enough of the
total is enclosed. That is what makes VAH and VAL prices you can trade against.

No I/O and no chart. Feed it two arrays; it hands back three prices.
"""

from __future__ import annotations

import numpy as np

from src.config import profile as cfg


class EmptyProfile(ValueError):
    """No volume traded, so there is no point of control to speak of."""


def value_area(prices: np.ndarray, volumes: np.ndarray,
               coverage: float = None) -> tuple[float, float, float]:
    """Return ``(poc, val, vah)`` - the point of control and the band around it.

    ``prices`` must be ascending and ``volumes`` aligned to them. Levels with no
    volume may be present or absent; both give the same answer.
    """
    coverage = cfg.VALUE_AREA if coverage is None else coverage
    if len(prices) == 0 or volumes.sum() <= 0:
        raise EmptyProfile("no volume at any price")

    total = float(volumes.sum())
    target = total * coverage

    # The point of control. On a tie, the level nearest the middle of the range
    # wins - an arbitrary rule, but a deterministic one, and it never picks an
    # edge just because that edge happened to be scanned first.
    peak = volumes.max()
    tied = np.flatnonzero(volumes == peak)
    middle = (len(prices) - 1) / 2.0
    poc_i = int(tied[np.argmin(np.abs(tied - middle))])

    lo = hi = poc_i
    inside = float(volumes[poc_i])

    while inside < target and (lo > 0 or hi < len(prices) - 1):
        # Look one level out on each side. Off the end contributes nothing, so a
        # profile that runs out of room on one side simply grows on the other.
        below = float(volumes[lo - 1]) if lo > 0 else -1.0
        above = float(volumes[hi + 1]) if hi < len(prices) - 1 else -1.0

        if above >= below:
            hi += 1
            inside += float(volumes[hi])
        else:
            lo -= 1
            inside += float(volumes[lo])

    return float(prices[poc_i]), float(prices[lo]), float(prices[hi])
