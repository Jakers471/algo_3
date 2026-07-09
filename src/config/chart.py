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

# Records the running server so a new one can reclaim the port instead of
# stacking behind it. Under cache/ because it is disposable runtime state.
PID_FILE = _ROOT / "cache" / "chart" / "server.pid"

# Seconds to wait for an old server to die, and for the port to come free.
SHUTDOWN_TIMEOUT = 5.0

# --- Bar cache --------------------------------------------------------------
# Packed, memmap-ready binary built from the Parquet store (git-ignored).
CACHE_DIR = _ROOT / "cache" / "chart"

# Symbols/timeframes the chart offers. A pair is listed only if its Parquet exists.
SYMBOLS = ("NQ", "ES")
TIMEFRAMES = ("1m", "5m", "15m", "60m", "1d")

# --- Wire -------------------------------------------------------------------
# Largest slice one /api/bars request may return, so a bad query can't ask for
# six million bars and stall the browser.
MAX_BARS_PER_REQUEST = 20_000

# --- Replay -----------------------------------------------------------------
# Bars kept behind the cursor. Enough to zoom out into real history without
# holding the whole dataset in the browser.
HISTORY_BARS = 5_000

# Once the client buffer exceeds this, the oldest bars are dropped.
MAX_BUFFER_BARS = 8_000

# How many bars to drop per trim. Trimming rebuilds the series, so do it in
# infrequent chunks rather than one bar at a time.
TRIM_CHUNK_BARS = 1_500

# Bars fetched ahead of the cursor, so stepping never waits on the network.
PREFETCH_BARS = 2_000

# Refetch when fewer than this many un-played bars remain buffered.
PREFETCH_THRESHOLD_BARS = 500

# Milliseconds between bars at 1x. 2x and 4x divide this.
BASE_STEP_MS = 500

# Refresh the indicator overlays every N revealed bars during replay. The server
# recomputes indicators over the whole revealed buffer (~58ms at 8,000 bars), so
# this is a cost/latency dial, not a correctness one - the drawing is always
# computed from bars at or before the cursor. Phase 5's server-side replay
# session makes it O(1) per bar and this dial goes away.
OVERLAY_REFRESH_BARS = 5
