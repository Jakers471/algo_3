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
  /api/overlays?symbol&timeframe&start&count -> JSON: drawing instructions
"""

from __future__ import annotations

import json
import logging

from src.chart import overlays, store
from src.config import chart as chart_cfg
from src.config.indicators import orderflow as orderflow_cfg
from src.config.indicators import profile as profile_cfg
from src.profile.build import paths as vap_paths

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
        if path == "/api/overlays":
            return _overlays(query)
    except store.NotPacked as exc:
        return _error(404, str(exc))
    except ValueError as exc:
        return _error(400, str(exc))
    except Exception:  # a bug here must not kill the server
        logger.exception("Unhandled error serving %s", path)
        return _error(500, "internal error - see server log")
    return _error(404, f"no such route: {path}")


def _profile_symbols() -> list[str]:
    """Symbols with a volume-at-price store, so the chart can say why not.

    A bar file records total volume and a high and a low; it cannot say where
    between them the contracts changed hands. Offering a profile on one and
    quietly drawing nothing is worse than not offering it - the user reads the
    empty chart as a bug, and the honest answer is that the data never existed.
    """
    with_vap = []
    for symbol in store.datasets():
        vap_path, idx_path = vap_paths(symbol, profile_cfg.BASE_TIMEFRAME)
        if vap_path.exists() and idx_path.exists():
            with_vap.append(symbol)
    return with_vap


def _config() -> dict:
    """The replay dials, served so config/chart.py stays the single source."""
    return {
        "bar_bytes": store.packer.BAR_DTYPE.itemsize,
        "history_bars": chart_cfg.HISTORY_BARS,
        "max_buffer_bars": chart_cfg.MAX_BUFFER_BARS,
        "trim_chunk_bars": chart_cfg.TRIM_CHUNK_BARS,
        "prefetch_bars": chart_cfg.PREFETCH_BARS,
        "base_step_ms": chart_cfg.BASE_STEP_MS,
        # The timeframe the volume-at-price store was folded at. A bar finer
        # than this cannot be profiled from it, and a bar that is not a whole
        # multiple of it would be attributed volume from bars either side.
        "profile_base_timeframe": profile_cfg.BASE_TIMEFRAME,
        # Which drawings the Layers panel offers, and which start visible. A
        # layer whose indicator is not drawing is not offered: the checkbox
        # would toggle marks that never arrive.
        "layers": [dict(layer) for layer in chart_cfg.LAYERS
                   if layer["id"] in overlays.drawable()],
        "max_bars_per_request": chart_cfg.MAX_BARS_PER_REQUEST,
        # Style lives in Python with the indicator, not in the browser.
        "orderflow": {
            "draw": orderflow_cfg.ENABLED and orderflow_cfg.DRAW_DELTA,
            "up_color": orderflow_cfg.DELTA_UP,
            "down_color": orderflow_cfg.DELTA_DOWN,
            "pane_top": orderflow_cfg.PANE_TOP,
            "pane_bottom": orderflow_cfg.PANE_BOTTOM,
        },
        # Which symbols can be profiled at all. Volume at price lives in the
        # ticks; a bar file has none, and none can be derived from it.
        "profile_symbols": _profile_symbols(),
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


def _overlays(query: dict) -> Response:
    """Indicator output for a bar range, as shapes the chart renders blindly.

    The caller passes the range it has REVEALED, so during replay the indicators
    never see a bar past the cursor and the drawing cannot leak the future.
    """
    symbol, timeframe = _pair(query)
    start = _int_arg(query, "start")
    n = _int_arg(query, "count", chart_cfg.PREFETCH_BARS)
    if n < 0:
        raise ValueError("'count' must not be negative")
    n = min(n, chart_cfg.MAX_BARS_PER_REQUEST)
    mode = query.get("profile", [None])[0]
    return _json(200, {"overlays": overlays.for_range(symbol, timeframe, start, n, mode)})
