"""Dials for the session-history percentile table.

A raw travel or volume number, even divided by range_scale, is not comparable
to one from two years ago - range_scale corrects for the regime the market is
in RIGHT NOW, not for whether the whole dataset's distribution has itself
drifted. A percentile rank against the SAME dataset's history at the SAME
elapsed bar count sidesteps that: 968 is not "big" or "small" in the
abstract, only relative to what usually happens by this point in a London or
NY session.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]

# The packed table: one file per (symbol, timeframe). Built by
# `python -m src.cli.session_history`; git-ignored, like the other caches.
CACHE_DIR = _ROOT / "cache" / "session_history"

# Percentile breakpoints stored per (session, elapsed bar, metric). 5% steps -
# fine enough to place a value usefully, coarse enough that the table stays a
# few hundred KB per symbol/timeframe rather than needing every raw session.
PERCENTILES = np.arange(0, 101, 5)
