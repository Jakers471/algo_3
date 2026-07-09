"""Trading-session configuration: timezone and regular trading hours.

One job: define how time and sessions are handled. Dictated by the audit's
`timezone` flag — store and compute everything in UTC internally; convert to
US/Eastern only for RTH session logic.
"""

from __future__ import annotations

from datetime import time

# Everything is stored and computed in UTC (audit: timezone, required).
INTERNAL_TZ = "UTC"

# Regular Trading Hours are defined in US/Eastern (09:30-16:00 ET).
RTH_TZ = "US/Eastern"
RTH_START = time(9, 30)
RTH_END = time(16, 0)

# Futures session model: three sessions per day. Windows are minute-of-day in
# SESSION_TZ; Asia wraps past midnight. The 17:00-18:00 gap is the daily CME
# maintenance halt (= 16:00-17:00 Chicago), during which no bars exist.
#
# SESSION_TZ is US/Eastern, and that is load-bearing. These windows are the
# standard Eastern session boundaries: the globex reopen at 18:00 ET, London's
# 03:00 ET open, the NY cash session, and the 17:00 ET close. Verified against
# the data: with US/Eastern every one of 143,013 bars falls in exactly one
# session; with America/Chicago, 5,764 real trading bars (the 17:00-18:00 ET
# hour) fall in NO session and are silently discarded, while the halt hour gets
# mislabelled as NY.
SESSION_TZ = "US/Eastern"
SESSIONS = [
    {"name": "Asia",   "start": 18 * 60, "end": 3 * 60},   # 18:00 -> 03:00 ET (wraps)
    {"name": "London", "start": 3 * 60,  "end": 8 * 60},   # 03:00 -> 08:00 ET
    {"name": "NY",     "start": 8 * 60,  "end": 17 * 60},  # 08:00 -> 17:00 ET
]

# Bars are CLOSE-stamped: a bar labelled T covers (T-step, T]. So a bar belongs
# to the session its interval CLOSED in, and session membership is
# ``start < minute <= end`` - left-open, right-closed, matching the bars.
# With ``minute < end`` instead, the 17:00 ET bar (NY's last) belongs nowhere.
SESSION_END_INCLUSIVE = True

MAX_SESSIONS = 60   # most-recent session instances to return
