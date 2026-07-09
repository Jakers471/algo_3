"""Turn indicator state into drawing instructions the chart can render blindly.

One job: decide what a row of indicator fields should draw. The chart drops a
labelled rule without knowing what a trading session is; if we later mark a
break of structure the same way, the frontend needs no change at all.

``marks_for`` is the single source of that decision. Browse mode walks a bar
range through it (``for_range``); replay calls it once per step, on the row the
live indicator state just produced. Both paths therefore draw identically -
which is the whole point of computing indicators once, in Python.

Overlay kinds (only what has a producer; more arrive with their indicators):
    vlines  - dashed rules with labels: [{time, label, color, labelColor}]
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from src.chart import store
from src.config.indicators import orderflow as orderflow_cfg
from src.config.indicators import sessions as sessions_cfg
from src.events.types import BarClose
from src.indicators.orderflow import OrderFlow
from src.indicators.registry import Registry
from src.indicators.sessions import Sessions

logger = logging.getLogger(__name__)


def build_registry() -> Registry:
    """The indicators that run. Add one here when it earns a place in the row."""
    indicators = []
    if sessions_cfg.ENABLED:
        indicators.append(Sessions())
    if orderflow_cfg.ENABLED:
        indicators.append(OrderFlow())
    return Registry(indicators)


def _optional(value) -> float | None:
    """NaN on the wire means ABSENT. Never let it become a number downstream."""
    return None if value is None or math.isnan(value) else float(value)


def bar_events(bars) -> list[BarClose]:
    """Structured bar records -> BarClose events, in order.

    Columns are pulled to Python lists once. Reading fields off numpy scalars
    per bar costs several times more than the indicator pass itself.
    """
    times = pd.to_datetime(bars["time"].astype("int64"), unit="s", utc=True)
    o, h = bars["open"].tolist(), bars["high"].tolist()
    lo, c, v = bars["low"].tolist(), bars["close"].tolist(), bars["volume"].tolist()
    d = bars["delta"].tolist()
    bv, sv = bars["buy_volume"].tolist(), bars["sell_volume"].tolist()
    tr = bars["trades"].tolist()
    return [BarClose(ts=t, open=o[i], high=h[i], low=lo[i], close=c[i], volume=v[i],
                     delta=_optional(d[i]), buy_volume=_optional(bv[i]),
                     sell_volume=_optional(sv[i]), trades=_optional(tr[i]))
            for i, t in enumerate(times)]


def marks_for(time: int, row: dict, *, is_first: bool = False) -> list[dict]:
    """The drawings this row produces. One row in, zero or more shapes out.

    ``is_first`` suppresses the boundary on the first row of any window. Every
    indicator starts with empty state, so its first event always reports
    ``session_new`` - a fact about the indicator waking up, not about the market
    opening a session. Drawing it would put a phantom rule at the left edge of
    every window we ever request.
    """
    marks: list[dict] = []
    if is_first:
        return marks

    if sessions_cfg.ENABLED and sessions_cfg.DRAW_BOUNDARIES and row.get("session_new"):
        name = row.get("session")
        if name is not None:      # entering the halt is not a session open
            marks.append({
                "kind": "vline",
                "time": int(time),
                "label": name,
                "color": sessions_cfg.LINE_COLORS.get(name, "rgba(125,133,144,0.6)"),
                "labelColor": sessions_cfg.LABEL_COLORS.get(name, "rgba(201,209,217,0.9)"),
            })
    return marks


def group_marks(marks: list[dict]) -> list[dict]:
    """Group flat marks into the overlay specs the frontend renders."""
    lines = [m for m in marks if m["kind"] == "vline"]
    return [{"id": "sessions", "kind": "vlines", "lines": lines}] if lines else []


def for_range(symbol: str, timeframe: str, start: int, count: int) -> list[dict]:
    """Overlay specs for bars ``[start, start+count)``. Used by browse mode.

    Indicators are fed only these bars, in order, so nothing in the output can
    depend on a bar after the last one requested.
    """
    bars = store.slice_bars(symbol, timeframe, start, count)
    if len(bars) == 0:
        return []

    registry = build_registry()
    registry.reset()

    marks: list[dict] = []
    for i, (bar, event) in enumerate(zip(bars, bar_events(bars))):
        row = registry.update(event)
        marks.extend(marks_for(int(bar["time"]), row, is_first=(i == 0)))
    return group_marks(marks)
