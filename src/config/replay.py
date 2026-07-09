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
