"""Historical bar retrieval from the ProjectX Gateway API.

One job: fetch OHLCV bars for a contract. Plumbing only — it returns the raw
bars the API gives back; shaping/analysis belongs elsewhere.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

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

# Named timeframes -> (unit, unit_number). Names match the saved CSV suffixes.
TIMEFRAMES = {
    "1m": (UNIT_MINUTE, 1),
    "5m": (UNIT_MINUTE, 5),
    "15m": (UNIT_MINUTE, 15),
    "60m": (UNIT_HOUR, 1),
    "1d": (UNIT_DAY, 1),
}


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


def _parse(t: str) -> datetime:
    """Parse an API bar timestamp (ISO-8601 with offset) to a datetime."""
    return datetime.fromisoformat(t)


def retrieve_history(
    client: ProjectXClient,
    contract_id: str,
    unit: int,
    unit_number: int = 1,
    live: bool = False,
    page_limit: int = MAX_BARS,
    earliest: datetime | None = None,
    pause: float = 0.65,
) -> list[dict]:
    """Page backward from now, collecting *all* available bars for a contract.

    The API caps each request at ``MAX_BARS`` and returns newest-first, so we
    walk backward: each page ends where the previous one began. Stops when a
    page returns fewer than ``page_limit`` bars (start of available history) or
    makes no further progress. Returns bars oldest-first, de-duplicated.

    ``pause`` seconds sleep between requests keeps us under the history
    endpoint's rate limit (50 req / 30s).
    """
    if earliest is None:
        earliest = datetime(2000, 1, 1, tzinfo=timezone.utc)
    cursor = datetime.now(timezone.utc)
    by_time: dict[str, dict] = {}
    page = 0
    while True:
        bars = retrieve_bars(
            client, contract_id, start=earliest, end=cursor,
            unit=unit, unit_number=unit_number, limit=page_limit, live=live,
        )
        page += 1
        if not bars:
            break
        new = 0
        oldest = cursor
        for bar in bars:
            key = bar["t"]
            if key not in by_time:
                by_time[key] = bar
                new += 1
            when = _parse(key)
            if when < oldest:
                oldest = when
        logger.info(
            "Page %d: +%d new (oldest %s), total %d.",
            page, new, oldest.isoformat(), len(by_time),
        )
        if len(bars) < page_limit:
            break  # reached the beginning of available history
        if new == 0 or oldest >= cursor:
            break  # no progress; stop rather than loop forever
        cursor = oldest
        time.sleep(pause)
    return sorted(by_time.values(), key=lambda b: b["t"])
