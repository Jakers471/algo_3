"""Turn indicator state into drawing instructions the chart can render blindly.

One job: run the registered indicators over a range of bars and emit overlay
specs - shapes and colors, no meaning. The chart drops a labelled rule without
knowing what a trading session is; if we later mark a break of structure the
same way, the frontend needs no change at all.

This is the seam that keeps the chart from computing anything. The indicator is
written once, in Python, and the browser receives the result.

Overlay kinds (only what has a producer; more arrive with their indicators):
    vlines  - dashed rules with labels: [{time, label, color, labelColor}]
"""

from __future__ import annotations

import logging

import pandas as pd

from src.chart import store
from src.config.indicators import sessions as sessions_cfg
from src.events.types import BarClose
from src.indicators.registry import Registry
from src.indicators.sessions import Sessions

logger = logging.getLogger(__name__)


def build_registry() -> Registry:
    """The indicators the chart draws. Add one here when it earns a drawing."""
    indicators = []
    if sessions_cfg.ENABLED:
        indicators.append(Sessions())
    return Registry(indicators)


def _events(bars) -> list[BarClose]:
    """Structured bar records -> BarClose events, in order.

    Columns are pulled to Python lists once. Reading fields off numpy scalars
    per bar costs several times more than the indicator pass itself.
    """
    times = pd.to_datetime(bars["time"].astype("int64"), unit="s", utc=True)
    o, h = bars["open"].tolist(), bars["high"].tolist()
    lo, c, v = bars["low"].tolist(), bars["close"].tolist(), bars["volume"].tolist()
    return [BarClose(ts=t, open=o[i], high=h[i], low=lo[i], close=c[i], volume=v[i])
            for i, t in enumerate(times)]


def for_range(symbol: str, timeframe: str, start: int, count: int) -> list[dict]:
    """Overlay specs for bars ``[start, start+count)``.

    Indicators are fed only these bars, in order, so nothing in the output can
    depend on a bar after the last one requested. During replay the caller passes
    exactly the revealed range, and the drawing cannot leak the future.
    """
    bars = store.slice_bars(symbol, timeframe, start, count)
    if len(bars) == 0:
        return []

    registry = build_registry()
    registry.reset()

    rows = [registry.update(event) for event in _events(bars)]
    overlays = []
    if sessions_cfg.ENABLED and sessions_cfg.DRAW_BOUNDARIES:
        lines = _session_boundaries(bars, rows)
        if lines:
            overlays.append({"id": "sessions", "kind": "vlines", "lines": lines})
    return overlays


def _session_boundaries(bars, rows: list[dict]) -> list[dict]:
    """A dashed rule at each session open.

    The FIRST row is skipped. Every indicator starts with empty state, so its
    first event always reports ``session_new`` - that is a fact about the
    indicator waking up, not about the market opening a session. Drawing it would
    put a phantom rule at the left edge of every window we ever request.
    """
    lines: list[dict] = []
    for i, (bar, row) in enumerate(zip(bars, rows)):
        if i == 0 or not row.get("session_new"):
            continue
        name = row.get("session")
        if name is None:      # entering the halt is not a session open
            continue
        lines.append({
            "time": int(bar["time"]),
            "label": name,
            "color": sessions_cfg.LINE_COLORS.get(name, "rgba(125,133,144,0.6)"),
            "labelColor": sessions_cfg.LABEL_COLORS.get(name, "rgba(201,209,217,0.9)"),
        })
    return lines
