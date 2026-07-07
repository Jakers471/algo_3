"""Historical bar retrieval from the ProjectX Gateway API.

One job: fetch OHLCV bars for a contract. Plumbing only — it returns the raw
bars the API gives back; shaping/analysis belongs elsewhere.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.broker.client import ProjectXClient

logger = logging.getLogger(__name__)

# Aggregation units the API understands.
UNIT_SECOND = 1
UNIT_MINUTE = 2
UNIT_HOUR = 3
UNIT_DAY = 4
UNIT_WEEK = 5
UNIT_MONTH = 6

MAX_BARS = 20_000  # API hard cap per request


def retrieve_bars(
    client: ProjectXClient,
    contract_id: str,
    start: datetime,
    end: datetime,
    unit: int,
    unit_number: int = 1,
    limit: int = 1_000,
    live: bool = False,
    include_partial_bar: bool = False,
) -> list[dict]:
    """Return a list of bar dicts (keys: t, o, h, l, c, v), newest first.

    ``start``/``end`` are datetimes; they are sent as ISO-8601 with a trailing Z.
    ``limit`` is capped at the API maximum of 20,000.
    """
    payload = {
        "contractId": contract_id,
        "live": live,
        "startTime": _iso(start),
        "endTime": _iso(end),
        "unit": unit,
        "unitNumber": unit_number,
        "limit": min(limit, MAX_BARS),
        "includePartialBar": include_partial_bar,
    }
    data = client.post("/api/History/retrieveBars", payload)
    if not data.get("success"):
        raise RuntimeError(f"History/retrieveBars failed (errorCode={data.get('errorCode')}).")
    bars = data.get("bars", [])
    logger.info("Retrieved %d bar(s) for %s.", len(bars), contract_id)
    return bars


def _iso(dt: datetime) -> str:
    """Format a datetime as ISO-8601 with a trailing Z (UTC)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
