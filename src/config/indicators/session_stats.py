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
# time, floored at RECENT_MIN_BARS bars. This is also N for the two-window
# (recent vs prior) phase-detection design SESSION_STATS_BRIEF.md calls for -
# one window, reused, not two unrelated dials.
#
# MEASURED, not borrowed. scratch/analysis/session_window_study.py walks every
# London/NY session in the NQT dataset (1,212 of them) and, per candidate N,
# counts recent/prior EFFICIENCY-ratio transitions (crossing outside [0.5, 2.0])
# and checks how many are confirmed by that same candidate's own 4N companion
# nearby - the same "does a coarser rung agree" check scale_ladder.py runs for
# RETRACE. On NQT 5m:
#
#     N (bars)   events   per 1k bars   confirmed by 4N
#          3        567         5.7         54.1%
#          4      1,203        12.2         52.9%
#          5      1,553        15.7         48.4%
#          6      1,694        17.1         44.0%   <- chosen
#          8      1,762        17.8         33.1%
#         10      1,681        17.0         24.1%
#
# Confirmation falls off SMOOTHLY as N grows, with no elbow or cliff - the same
# finding scale_ladder.py made for RETRACE (H = 0.503: no privileged scale).
# So this is not "the true N," it is a considered point on a tradeoff that has
# no true optimum: N=6 sits near peak event count (power, sqrt(n)) while still
# confirming a real plurality of its own events, clearly ahead of N=8/10's
# fall-off. On 5m bars N=6 is 30 minutes - which is also what this dial already
# held, provisionally, before it was ever measured.
RECENT_WINDOW_MINUTES = 30
RECENT_MIN_BARS = 6

# --- the session's own volume profile ----------------------------------------
# Bin width = range_scale / BINS_PER_SCALE, same reasoning as
# config/indicators/profile.py: a session spans hours, not a leg's few dozen
# bars, so a coarser or finer count than profile's own dial may read better -
# they are independent, not duplicated.
BINS_PER_SCALE = 8

# --- shelves and gaps: HVN/LVN --------------------------------------------------
# A bin qualifies as an HVN only if it is a strict local peak AND carries at
# least this share of the POC's own volume - a real shelf, not a one-bin
# wobble one tick either side of it. 0.5 means "half as loud as the fair
# price" - loud enough that a stop placed behind it is resting on real
# acceptance, not on noise the next bar erases.
HVN_MIN_SHARE = 0.5

# A bin qualifies as an LVN only if it is a strict local trough AND carries at
# most this share of the POC's own volume - a real gap the market moved
# through fast, not an ordinary thin bin at the edge of the range. 0.15 keeps
# it well below "unremarkable" rather than merely "less than the peak."
LVN_MAX_SHARE = 0.15

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
