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
