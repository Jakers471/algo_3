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

# Futures session model (CME exchange time) used by the volume-profile / GRADE
# side: three sessions per day. Windows are minute-of-day in SESSION_TZ; Asia
# wraps past midnight. The 17:00-18:00 gap is the daily maintenance halt.
SESSION_TZ = "America/Chicago"
SESSIONS = [
    {"name": "Asia",   "start": 18 * 60, "end": 3 * 60},   # 18:00 -> 03:00 (wraps)
    {"name": "London", "start": 3 * 60,  "end": 8 * 60},   # 03:00 -> 08:00
    {"name": "NY",     "start": 8 * 60,  "end": 17 * 60},  # 08:00 -> 17:00
]
MAX_SESSIONS = 60   # most-recent session instances to return
