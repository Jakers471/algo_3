"""Dials for the session_stats indicator - the running session scorecard.

VPbreakout trades London and NY only. This indicator exists to measure those
two sessions live, from open to now, so the numbers on the card are exactly
what a live feed would have shown at that instant - never a proxy computed
after the fact.

Asia and the maintenance halt are out of scope for that strategy, so this
indicator refuses on them: publishing a "session so far" for a session nobody
intends to trade would only invite a rule to accidentally read it.
"""

from __future__ import annotations

ENABLED = True

# Which sessions.py names this indicator accumulates for. Every other session
# name (including the halt, which is None) is out of scope: reset happens, but
# nothing is published - Unavailable, not a zero-filled row for a session no
# rule should be reading.
TRACKED_SESSIONS = ("London", "NY")

# --- the recent window ---------------------------------------------------------
# session_delta_recent sums delta over the last RECENT_WINDOW_MINUTES of market
# time, floored at RECENT_MIN_BARS bars - the same shape as range_scale's own
# window, and the same numbers, reused rather than re-derived: 30 minutes is
# the shortest window that still leaves the fastest rungs a real sample, and
# there is no basis yet to pick a different one for delta specifically.
#
# PROVISIONAL. This is not the two-window (recent vs prior) phase-detection
# design that replaces session_efficiency/session_dir_changes/session_travel -
# that needs an N chosen by measuring event count and lag across a small
# geometric ladder (N, 2N, 4N), the way swing.py's RETRACE was chosen, never
# by eye and never by optimizing PnL. Delta alone doesn't need that ladder - it
# only needs to stop blending across regimes - so it borrows range_scale's
# already-justified window rather than inventing a fresh unvalidated number.
RECENT_WINDOW_MINUTES = 30
RECENT_MIN_BARS = 8

# --- the session's own volume profile ----------------------------------------
# Bin width = range_scale / BINS_PER_SCALE, same reasoning as
# config/indicators/profile.py: a session spans hours, not a leg's few dozen
# bars, so a coarser or finer count than profile's own dial may read better -
# they are independent, not duplicated.
BINS_PER_SCALE = 8

# --- drawing -------------------------------------------------------------
DRAW = True

# Each bin is a horizontal bar anchored at the session's right edge (now) and
# growing left toward the open, the heaviest reaching this many PIXELS. See
# config/indicators/profile.py MAX_WIDTH_PX for why pixels and not a time span.
MAX_WIDTH_PX = 170

# Bought at the ask, sold at the bid - the same green and red as the candles,
# the delta strip, and profile.py's own bins. One colour language for the
# whole chart; a session profile drawn in a different hue would claim this is
# a different kind of measurement; it is the same one, over a wider range.
BUY_COLOR = "rgba(38, 166, 154, 0.45)"
SELL_COLOR = "rgba(239, 83, 80, 0.45)"

POC_COLOR = "#d29922"
VALUE_AREA_COLOR = "rgba(210, 153, 34, 0.40)"

BIN_HEIGHT = 1
POC_WIDTH = 2
