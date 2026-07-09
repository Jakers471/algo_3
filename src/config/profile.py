"""Dials for the volume profile - volume at price, and the value area drawn from it.

A profile is a histogram of traded volume against price. A bar file cannot supply
one: it records a bar's total volume and its high and low, never where inside that
range the contracts changed hands. Spreading a bar's volume across its range would
be a fabrication, so the profile is built from the tick file, once, into a packed
store that the chart slices.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

# The packed store: one record per (base bar, price level). Built by
# `python -m src.cli.vap`; git-ignored, like the bar cache it sits beside.
CACHE_DIR = _ROOT / "cache" / "vap"

# Bins are ONE TICK wide, and that is not a choice - it is the finest the market
# can resolve, and every coarser binning is an exact fold of it. Verified: after
# back-adjustment, 100.00% of tick prices land on the 0.25 grid.
TICK_SIZE = 0.25

# The share of volume inside the value area. 70% is the convention (roughly one
# standard deviation of a normal), and it is a convention, not a law.
VALUE_AREA = 0.70
