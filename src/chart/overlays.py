"""Turn indicator state into drawing instructions the chart can render blindly.

One job: decide what a row of indicator fields should draw. The chart drops a
labelled rule without knowing what a trading session is; if we later mark a
break of structure the same way, the frontend needs no change at all.

``marks_for`` is the single source of that decision. Browse mode walks a bar
range through it (``for_range``); replay calls it once per step, on the row the
live indicator state just produced. Both paths therefore draw identically -
which is the whole point of computing indicators once, in Python.

Overlay kinds (only what has a producer; more arrive with their indicators):
    vlines   - dashed rules with labels:  [{time, label, color, labelColor}]
    markers  - a dot on a bar:            [{time, position, color, shape, text}]
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from src.chart import store
from src.config.indicators import absorption as absorption_cfg
from src.config.indicators import breaks as breaks_cfg
from src.config.indicators import legs as legs_cfg
from src.config.indicators import orderflow as orderflow_cfg
from src.config.indicators import range_scale as range_scale_cfg
from src.config.indicators import sessions as sessions_cfg
from src.config.indicators import swing as swing_cfg
from src.events.types import BarClose
from src.indicators.absorption import Absorption
from src.indicators.breaks import Breaks
from src.indicators.legs import Legs
from src.indicators.orderflow import OrderFlow
from src.indicators.range_scale import RangeScale
from src.indicators.registry import Registry
from src.indicators.sessions import Sessions
from src.indicators.swing import Swing

logger = logging.getLogger(__name__)


def build_registry() -> Registry:
    """The indicators that run. Add one here when it earns a place in the row."""
    indicators = []
    if sessions_cfg.ENABLED:
        indicators.append(Sessions())
    if orderflow_cfg.ENABLED:
        indicators.append(OrderFlow())
    if absorption_cfg.ENABLED:
        indicators.append(Absorption())
    # A dial that turns something off must not break what depends on it. legs and
    # breaks are built from swing points; swing measures its threshold in
    # multiples of range_scale. Enabling a consumer enables what it consumes -
    # otherwise the registry raises on a missing dependency and the dial is a trap.
    wants_swing = swing_cfg.ENABLED or legs_cfg.ENABLED or breaks_cfg.ENABLED
    if range_scale_cfg.ENABLED or wants_swing:
        indicators.append(RangeScale())
    if wants_swing:
        indicators.append(Swing())
    if legs_cfg.ENABLED:
        indicators.append(Legs())
    if breaks_cfg.ENABLED:
        indicators.append(Breaks())
    # The registry topologically sorts by declared dependencies, so the order
    # they are appended in here does not matter.
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


def _segment(source: str, points: list[tuple], color: str, width: int) -> dict:
    """A polyline in (time, price) space, for the chart to stroke.

    ``time`` is the EARLIEST point, because that is what the replay trim filter
    compares against: a segment whose left end has scrolled out of the buffer
    cannot be drawn, so it should be dropped rather than half-drawn.
    """
    return {
        "kind": "segment",
        "source": source,
        "time": int(min(t for t, _ in points)),
        "points": [{"time": int(t), "price": float(p)} for t, p in points],
        "color": color,
        "width": width,
    }


def marks_for(time: int, row: dict, *, is_first: bool = False,
              close: float | None = None) -> list[dict]:
    """The drawings this row produces. One row in, zero or more shapes out.

    ``is_first`` suppresses the boundary on the first row of any window. Every
    indicator starts with empty state, so its first event always reports
    ``session_new`` - a fact about the indicator waking up, not about the market
    opening a session. Drawing it would put a phantom rule at the left edge of
    every window we ever request.

    ``close`` is this bar's close, needed only to land the vertical stroke of a
    break on the price that went through the level. Absent, the break is drawn as
    the horizontal alone.
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

    if absorption_cfg.ENABLED and absorption_cfg.DRAW_MARKERS and row.get("absorption"):
        side = row.get("absorption_side")
        buying = side == "buy"
        marks.append({
            "kind": "marker",
            "source": "absorption",
            "time": int(time),
            # Buyers absorbed: the resting interest is UNDER the bar. Mark it there.
            "position": "belowBar" if buying else "aboveBar",
            "color": (absorption_cfg.BUY_ABSORPTION_COLOR if buying
                      else absorption_cfg.SELL_ABSORPTION_COLOR),
            "shape": absorption_cfg.MARKER_SHAPE,
            "text": "",
        })

    if swing_cfg.ENABLED and swing_cfg.DRAW_MARKERS and row.get("swing"):
        is_high = row["swing"] == "high"
        marks.append({
            "kind": "marker",
            "source": "swing",
            # The bar that MADE the extreme, not the later bar that confirmed it.
            # A swing is always stamped in the past; that is what "confirmed"
            # costs. The mark therefore lands on the high it names.
            "time": int(row["swing_time"]),
            "position": "aboveBar" if is_high else "belowBar",
            "color": swing_cfg.MARKER_COLOR,
            "shape": swing_cfg.HIGH_SHAPE if is_high else swing_cfg.LOW_SHAPE,
            "text": "",
        })

    if legs_cfg.ENABLED and legs_cfg.DRAW and row.get("leg"):
        up = row["leg"] == "up"
        # Square corners: run along the price we left, then turn into the price
        # we arrived at. A diagonal would claim price travelled in a straight
        # line between the swings. The candles in between already say otherwise.
        marks.append(_segment(
            "legs",
            [(row["leg_from_time"], row["leg_from_price"]),
             (row["leg_to_time"], row["leg_from_price"]),
             (row["leg_to_time"], row["leg_to_price"])],
            legs_cfg.UP_COLOR if up else legs_cfg.DOWN_COLOR,
            legs_cfg.WIDTH,
        ))

    if breaks_cfg.ENABLED and breaks_cfg.DRAW and row.get("bos"):
        up = row["bos"] == "up"
        level = row["bos_level"]
        # Along the level from the swing that set it, to the bar that closed
        # through it - then down (or up) to that close.
        points = [(row["bos_time"], level), (int(time), level)]
        if close is not None:
            points.append((int(time), close))
        marks.append(_segment(
            "breaks", points,
            breaks_cfg.UP_COLOR if up else breaks_cfg.DOWN_COLOR,
            breaks_cfg.WIDTH,
        ))
    return marks


def group_marks(marks: list[dict]) -> list[dict]:
    """Group flat marks into the overlay specs the frontend renders.

    Markers are grouped by the indicator that produced them, so a spec stays
    named after one job. The frontend concatenates them regardless - it renders
    shapes, not meanings - but a spec called "absorption" that also carried swing
    points would be a lie to the next reader.
    """
    specs = []
    lines = [m for m in marks if m["kind"] == "vline"]
    if lines:
        specs.append({"id": "sessions", "kind": "vlines", "lines": lines})

    markers = [m for m in marks if m["kind"] == "marker"]
    for source in dict.fromkeys(m.get("source", "markers") for m in markers):
        group = [m for m in markers if m.get("source", "markers") == source]
        specs.append({"id": source, "kind": "markers", "markers": group})

    segments = [m for m in marks if m["kind"] == "segment"]
    for source in dict.fromkeys(m["source"] for m in segments):
        group = [m for m in segments if m["source"] == source]
        specs.append({"id": source, "kind": "segments", "segments": group})
    return specs


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
        marks.extend(marks_for(int(bar["time"]), row, is_first=(i == 0),
                               close=float(bar["close"])))
    return group_marks(marks)
