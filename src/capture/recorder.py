"""Record the live market feed verbatim, so we can learn what it actually sends.

One job: take raw hub events and append them to a JSON Lines file, exactly as
received, with a local receipt timestamp. It interprets nothing.

Why verbatim: the ProjectX docs name the events (GatewayTrade, GatewayQuote)
but do not document their payload fields. We cannot design the live event
source against a schema we are guessing at. So we record first, read the
recording, and write the adapter against what the feed really sends.

The recording is also the fixture: replaying a captured session drives the live
code path with zero network, and diffing a captured session against the
NinjaTrader tick export for the same clock is the only way to know whether the
two sources agree on trades, sizes, and quote staleness.

One line per event:
    {"recv": "2026-07-09T03:51:02.481123+00:00", "event": "GatewayTrade",
     "contract": "CON.F.US.ENQ.U26", "payload": <whatever the hub sent>}

`recv` is OUR clock at receipt, not the exchange's. It is not a substitute for
an exchange timestamp inside the payload - it exists to measure latency and to
order events when the payload has no usable time field.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.config import live as live_cfg

logger = logging.getLogger(__name__)


def session_path(contract_id: str, started: datetime | None = None) -> Path:
    """A unique, sortable file for one capture session."""
    started = started or datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    safe = contract_id.replace(".", "_")
    return live_cfg.CAPTURE_DIR / f"{stamp}_{safe}.jsonl"


class Recorder:
    """Append raw hub events to a JSON Lines file. Use as a context manager."""

    def __init__(self, contract_id: str, path: Path | None = None) -> None:
        self.contract_id = contract_id
        self.path = path or session_path(contract_id)
        self.counts: Counter = Counter()
        self._fh = None
        self._since_flush = 0

    def __enter__(self) -> Recorder:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")
        logger.info("Recording to %s", self.path)
        return self

    def __exit__(self, *_exc) -> None:
        if self._fh:
            self._fh.flush()
            self._fh.close()
            self._fh = None
        logger.info("Recorded %d events: %s", sum(self.counts.values()), dict(self.counts))

    def handle(self, event_name: str, payload) -> None:
        """The sink handed to MarketHub.on_event()."""
        if self._fh is None:
            raise RuntimeError("Recorder used outside its context manager")

        self.counts[event_name] += 1
        line = {
            "recv": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            "contract": self.contract_id,
            "payload": payload,
        }
        # default=str so an unexpected non-JSON type degrades to a string
        # rather than killing a live capture we may not get a second chance at.
        self._fh.write(json.dumps(line, default=str) + "\n")

        self._since_flush += 1
        if self._since_flush >= live_cfg.FLUSH_EVERY:
            self._fh.flush()
            self._since_flush = 0
