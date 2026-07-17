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

from datetime import date
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[2]

# --- the vault ---------------------------------------------------------------
# Sessions starting on or after this date are SEALED: held back, never looked
# at, never fit against. They are the one honest test this project will ever
# get, and they only stay honest while nobody opens them.
#
# Why a DATE and not a random sample: volatility clusters, so a randomly
# held-out Wednesday sits beside a Tuesday that explored it and leaks straight
# through. A time split asks the only question that pays - does this survive
# into a future it has never seen.
#
# Why a ROUND date and not a computed fraction: 2025-10-01 cuts NQT 5m
# (2024-03 -> 2026-07) at roughly the two-thirds mark (~810 sessions explore,
# ~400 sealed). It is a round date near that fraction and nothing more - there
# is no reason to tune it, and tuning it would itself be a look at the vault.
#
# This is the DECLARATION. The frozen RECEIPT of what it seals - counts,
# spans, the exact rule - is SESSION_SPLIT.json at the repo root, written once
# by scratch/session_research/seal_split.py; session_history/split.py verifies the two
# agree on every load, so neither can drift without a loud error.
SEALED_FROM = date(2025, 10, 1)

# The packed table: one file per (symbol, timeframe). Built by
# `python -m src.cli.session_history`; git-ignored, like the other caches.
CACHE_DIR = _ROOT / "cache" / "session_history"

# Percentile breakpoints stored per (session, elapsed bar, metric). 5% steps -
# fine enough to place a value usefully, coarse enough that the table stays a
# few hundred KB per symbol/timeframe rather than needing every raw session.
PERCENTILES = np.arange(0, 101, 5)
