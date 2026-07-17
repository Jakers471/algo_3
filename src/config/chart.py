"""Settings for the chart server and its replay engine.

One job: hold the dials the chart area runs on - where the packed bar cache
lives, what the server binds to, and how many bars the replay keeps resident.
No logic; the modules that act on these values read them from here.
"""

from __future__ import annotations

from pathlib import Path

# Repo root: src/config/chart.py -> parents[2].
_ROOT = Path(__file__).resolve().parents[2]

# --- Server -----------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8765

# The static frontend the server hands out (top-level, never inside src/).
FRONTEND_DIR = _ROOT / "frontend" / "chart"

# Records each running server so a new one can reclaim its port instead of
# stacking behind it. Under cache/ because it is disposable runtime state.
# One file PER PORT: a single pidfile can only ever describe one server, and a
# second server on another port would overwrite it - after which --stop would
# read a stale record and kill the wrong process.
PID_DIR = _ROOT / "cache" / "chart"

# Seconds to wait for an old server to die, and for the port to come free.
SHUTDOWN_TIMEOUT = 5.0

# --- Bar cache --------------------------------------------------------------
# Packed, memmap-ready binary built from the Parquet store (git-ignored).
CACHE_DIR = _ROOT / "cache" / "chart"

# Symbols/timeframes the chart offers. A pair is listed only if its Parquet exists.
# NQT is rebuilt from ticks (2024-03 -> 2026-07) and carries 15s; NQ/ES are the
# NT8 bar files (2005 -> 2025-01). They are separate datasets, not one series.
SYMBOLS = ("NQ", "ES", "NQT")
TIMEFRAMES = ("15s", "30s", "1m", "5m", "15m", "60m", "4h", "1d")

# --- Wire -------------------------------------------------------------------
# Largest slice one /api/bars request may return, so a bad query can't ask for
# six million bars and stall the browser.
MAX_BARS_PER_REQUEST = 20_000

# --- Replay -----------------------------------------------------------------
# Bars of history the server warms its indicators over when you cut back, and
# the browser draws behind the cursor. Enough to zoom out into real context
# without holding the whole dataset.
HISTORY_BARS = 5_000

# Once the client buffer exceeds this, the oldest bars are dropped.
MAX_BUFFER_BARS = 8_000

# How many bars to drop per trim. Trimming rebuilds the series, so do it in
# infrequent chunks rather than one bar at a time.
TRIM_CHUNK_BARS = 1_500

# Bars pulled per chunk when browse mode backfills older history on scroll-back.
PREFETCH_BARS = 2_000

# Milliseconds between bars at 1x. 2x and 4x divide this. The SERVER paces
# playback, so this is the real clock, not a hint to the browser.
BASE_STEP_MS = 500


# --- Overlay layers ----------------------------------------------------------
# What the chart's Layers panel offers, and what it shows on a fresh browser.
#
# This is VISIBILITY, not computation. Each indicator's own `ENABLED`/`DRAW` in
# config/indicators/ decides whether a mark is produced at all; these decide
# whether a produced mark is drawn. Hiding a layer costs the server nothing and
# the table nothing - the row still carries every field - so the chart and the
# snapshot table can never disagree about what was computed, only about what is
# on screen.
#
# `id` is the mark's `source`, which is how the browser filters without knowing
# what a leg or a session is. Add an indicator that draws, add a line here.
LAYERS = (
    # The session rules: a dashed vertical at each session open (Asia/London/NY),
    # on every symbol - pure time, so NQ/ES/NQT all get them. On by default; toggle
    # off in the Layers panel if three verticals a day is more ink than you want.
    {"id": "sessions",   "label": "Sessions",   "visible": True},
    {"id": "swing",      "label": "Swings",     "visible": True},
    {"id": "legs",       "label": "Legs",       "visible": True},
    {"id": "breaks",     "label": "Breaks",     "visible": True},
    {"id": "extremes",   "label": "Rails",      "visible": True},
    {"id": "absorption", "label": "Absorption", "visible": True},
    {"id": "ribbon",     "label": "MA ribbon",  "visible": False},
    {"id": "ma",         "label": "Moving averages", "visible": True},
    # Regime ships two shapes on one toggle: the dashed rule at each turn and
    # the background tint per bar (config/indicators/regime.py BAND_COLORS).
    {"id": "regime",     "label": "Regime",     "visible": False},
)
