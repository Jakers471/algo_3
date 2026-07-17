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
