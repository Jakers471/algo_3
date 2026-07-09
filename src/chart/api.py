"""Answer the chart's data questions. Transport-free.

One job: map a parsed request (path + query dict) to a response tuple of
``(status, content_type, body_bytes, extra_headers)``. It reads through
store.py and never touches sockets - server.py owns HTTP, this owns meaning.
Keeping them apart means the routes are testable without binding a port.

Routes:
  /api/config                            -> JSON: the replay dials the client obeys
  /api/datasets                          -> JSON: symbols/timeframes on offer
  /api/bars?symbol&timeframe&start&count -> raw bars (application/octet-stream)
  /api/locate?symbol&timeframe&time      -> JSON: bar index for an epoch second
"""

from __future__ import annotations

import json
import logging

from src.chart import store
from src.config import chart as chart_cfg

logger = logging.getLogger(__name__)

JSON = "application/json"
BINARY = "application/octet-stream"

Response = tuple[int, str, bytes, dict]


def _json(status: int, payload: dict) -> Response:
    return status, JSON, json.dumps(payload).encode(), {}


def _error(status: int, message: str) -> Response:
    return _json(status, {"error": message})


def _int_arg(query: dict, name: str, default: int | None = None) -> int:
    raw = query.get(name, [None])[0]
    if raw is None:
        if default is None:
            raise ValueError(f"missing required query param '{name}'")
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"query param '{name}' must be an integer, got {raw!r}") from None


def _pair(query: dict) -> tuple[str, str]:
    symbol = (query.get("symbol", [""])[0] or "").upper()
    timeframe = (query.get("timeframe", [""])[0] or "").lower()
    if not symbol or not timeframe:
        raise ValueError("both 'symbol' and 'timeframe' are required")
    return symbol, timeframe


def handle(path: str, query: dict) -> Response:
    """Route one API request. Never raises; failures come back as JSON errors."""
    try:
        if path == "/api/config":
            return _json(200, _config())
        if path == "/api/datasets":
            return _json(200, store.datasets())
        if path == "/api/bars":
            return _bars(query)
        if path == "/api/locate":
            return _locate(query)
    except store.NotPacked as exc:
        return _error(404, str(exc))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:  # a bug here must not kill the server
        logger.exception("Unhandled error serving %s", path)
        return _error(500, "internal error - see server log")
    return _error(404, f"no such route: {path}")


def _config() -> dict:
    """The replay dials, served so config/chart.py stays the single source."""
    return {
        "bar_bytes": store.packer.BAR_DTYPE.itemsize,
        "history_bars": chart_cfg.HISTORY_BARS,
        "max_buffer_bars": chart_cfg.MAX_BUFFER_BARS,
        "trim_chunk_bars": chart_cfg.TRIM_CHUNK_BARS,
        "prefetch_bars": chart_cfg.PREFETCH_BARS,
        "prefetch_threshold_bars": chart_cfg.PREFETCH_THRESHOLD_BARS,
        "base_step_ms": chart_cfg.BASE_STEP_MS,
        "max_bars_per_request": chart_cfg.MAX_BARS_PER_REQUEST,
    }


def _bars(query: dict) -> Response:
    """A raw slice of the packed cache. The bytes ARE the memmap contents."""
    symbol, timeframe = _pair(query)
    start = _int_arg(query, "start")
    n = _int_arg(query, "count", chart_cfg.PREFETCH_BARS)
    if n < 0:
        raise ValueError("'count' must not be negative")
    n = min(n, chart_cfg.MAX_BARS_PER_REQUEST)

    body, clamped_start = store.slice_bytes(symbol, timeframe, start, n)
    headers = {
        # The client needs these to place the slice: it asked for `start`, but a
        # clamp may have moved it, and the payload length gives the true count.
        "X-Start": str(clamped_start),
        "X-Count": str(len(body) // store.packer.BAR_DTYPE.itemsize),
        "X-Total": str(store.count(symbol, timeframe)),
        "Cache-Control": "no-store",
    }
    return 200, BINARY, body, headers


def _locate(query: dict) -> Response:
    """Snap a timestamp to a bar index, for date jumps and click-to-replay."""
    symbol, timeframe = _pair(query)
    epoch = _int_arg(query, "time")
    idx = store.locate(symbol, timeframe, epoch)
    return _json(200, {"index": idx, "total": store.count(symbol, timeframe)})
