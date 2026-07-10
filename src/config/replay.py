"""Dials for the server-side replay session.

One job: hold the settings the replay engine runs on. Pacing (how fast a bar
arrives) is shared with the chart's dials in ``config/chart.py``; these are the
ones only the session cares about.
"""

from __future__ import annotations

# Drop a session this many seconds after its last subscriber leaves. Long enough
# to survive a page refresh, short enough that an abandoned tab does not pin
# indicator state forever.
SESSION_IDLE_TIMEOUT = 300.0

# How often the reaper sweeps for idle sessions.
REAP_INTERVAL = 30.0

# Snapshots buffered per subscriber. A subscriber that falls this far behind is
# not worth waiting for - drop the oldest rather than stall the whole session,
# because a stalled session stalls every other subscriber too.
SUBSCRIBER_QUEUE_MAX = 512

# Seconds between SSE comment frames when nothing is happening. Proxies and
# browsers close a silent stream; a comment costs 2 bytes and prevents it.
SSE_KEEPALIVE_SECONDS = 15.0

# Playback speeds the server will honour.
SPEEDS = (1, 2, 4)


# --- the ladder --------------------------------------------------------------
# Timeframes to run ALONGSIDE the replay's own, folded from its bars, each with
# its own indicator state. A rung is only built if it is a whole multiple of the
# base timeframe: 30s folds into 3m and 15m exactly, and into nothing else.
#
# These three are evenly spaced in LOG time, which is the spacing that matters:
# a bar's range grows as t^0.507, so 30s -> 3m -> 15m are three steps of the same
# size through volatility, where 30s -> 5m -> 15m are not. See
# scratch/analysis/timeframe_scaling.html.
#
# One cursor drives all of them, so a 15m row lands on the same clock tick as the
# thirtieth 30s row. Nothing coordinates them; the arithmetic does.
LADDER = ("30s", "3m", "15m")
