"""Live market-data settings.

One job: hold the dials for the real-time feed - which contract to listen to,
which streams to subscribe, and where captured events land. No logic; the
modules that act on these read them from here.
"""

from __future__ import annotations

from pathlib import Path

# Repo root: src/config/live.py -> parents[2].
_ROOT = Path(__file__).resolve().parents[2]

# --- what to listen to ------------------------------------------------------
# The front-month NQ contract. Contract ids roll quarterly, so this is a dial,
# not a constant - resolve it with broker.contracts.search_contracts('NQ').
DEFAULT_CONTRACT_ID = "CON.F.US.ENQ.U26"

# Market-hub streams. 'trades' and 'quotes' together reproduce the NinjaTrader
# tick row (a trade with the prevailing bid/ask stamped on it). 'depth' is the
# full DOM - high volume, off by default.
SUBSCRIBE_TRADES = True
SUBSCRIBE_QUOTES = True
SUBSCRIBE_DEPTH = False

# --- capture ----------------------------------------------------------------
# Raw events land here as JSON Lines, one file per session (git-ignored).
CAPTURE_DIR = _ROOT / "capture"

# Flush to disk every N events. Small, because a capture that dies in a crash
# and takes its buffer with it has recorded nothing.
FLUSH_EVERY = 50

# --- connection -------------------------------------------------------------
# Seconds. signalrcore pings to keep the websocket alive.
KEEPALIVE_INTERVAL = 10
RECONNECT_ATTEMPTS = 5
RECONNECT_INTERVAL = 5
