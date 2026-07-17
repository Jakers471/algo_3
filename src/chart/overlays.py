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
    bands    - a bar slot's background:   [{time, color}]
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from src.chart import store
from src.config.indicators import absorption as absorption_cfg
from src.config.indicators import breaks as breaks_cfg
from src.config.indicators import legs as legs_cfg
from src.config.indicators import ma as ma_cfg
from src.config.indicators import orderflow as orderflow_cfg
from src.config.indicators import profile as profile_cfg
from src.config.indicators import range_scale as range_scale_cfg
from src.config.indicators import regime as regime_cfg
from src.config.indicators import ribbon as ribbon_cfg
from src.config.indicators import session_stats as session_stats_cfg
from src.config.indicators import sessions as sessions_cfg
from src.config.indicators import swing as swing_cfg
from src.events.types import BarClose
from src.indicators.absorption import Absorption
from src.indicators.breaks import Breaks
from src.indicators.legs import Legs
from src.indicators.ma import MA
from src.indicators.orderflow import OrderFlow
from src.indicators.profile import Profile
from src.indicators.range_scale import RangeScale
from src.indicators.regime import Regime
from src.indicators.registry import Registry
from src.indicators.ribbon import Ribbon
from src.indicators.session_stats import SessionStats
from src.indicators.sessions import Sessions
from src.indicators.swing import Swing
from src.profile import store as store_vap

logger = logging.getLogger(__name__)


def build_registry(profile_mode: str | None = None) -> Registry:
    """The indicators that run. Add one here when it earns a place in the row.

    ``profile_mode`` is "on" or "off" for one request, which is how the chart's
    toolbar runs the volume profile without editing a file. Off runs no profile
    indicator at all, and its volume-at-price lookups are never paid for.
    """
    indicators = []
    if sessions_cfg.ENABLED:
        indicators.append(Sessions())
    if session_stats_cfg.ENABLED:
        indicators.append(SessionStats())
    if orderflow_cfg.ENABLED:
        indicators.append(OrderFlow())
    if absorption_cfg.ENABLED:
        indicators.append(Absorption())
    # A dial that turns something off must not break what depends on it. legs and
    # breaks are built from swing points; swing measures its threshold in
    # multiples of range_scale. Enabling a consumer enables what it consumes -
    # otherwise the registry raises on a missing dependency and the dial is a trap.
    wants_swing = swing_cfg.ENABLED or legs_cfg.ENABLED or breaks_cfg.ENABLED
    # regime reads the ribbon and range_scale, so enabling it enables both -
    # otherwise the registry raises on a missing dependency and the dial is a trap.
    wants_ribbon = ribbon_cfg.ENABLED or regime_cfg.ENABLED
    if (range_scale_cfg.ENABLED or wants_swing or regime_cfg.ENABLED
            or session_stats_cfg.ENABLED):
        indicators.append(RangeScale())
    if wants_swing:
        indicators.append(Swing())
    if legs_cfg.ENABLED:
        indicators.append(Legs())
    if breaks_cfg.ENABLED:
        indicators.append(Breaks())
    if wants_ribbon:
        indicators.append(Ribbon())
    if regime_cfg.ENABLED:
        indicators.append(Regime())
    if ma_cfg.ENABLED and ma_cfg.ACTIVE:
        indicators.append(MA())

    if profile_cfg.ENABLED and (profile_mode or "off") != "off":
        indicators.append(Profile())
    # The registry topologically sorts by declared dependencies, so the order
    # they are appended in here does not matter.
    return Registry(indicators)


def wants_vap(registry: Registry, session_profile_mode: str | None = None) -> bool:
    """Does anything running in this registry read a bar's volume at price?

    A store lookup per bar is not free - fetching it for every request made a
    5,000-bar browse window take minutes, which is why each reader is gated by
    its OWN toolbar switch rather than fetching unconditionally.

    `profile` only ever runs when its switch is on (`build_registry` never
    builds it otherwise), so `registry.has("profile")` already says everything
    it needs to. `session_stats` is different: it runs unconditionally - its
    range/net/travel/volume/delta fields need no volume at price at all - so a
    SEPARATE switch, `session_profile_mode`, decides whether its own
    POC/VAL/VAH/bins get fed. Two independent switches, not one shared: a user
    who wants only the session's profile and not the swing one (or the other
    way round) can have exactly that, and neither pays for the other's fetch.

    The one asymmetry: if `profile` is ALREADY paying for the fetch, session_stats
    rides along on the same bars for free, even with its own switch off - there
    is no second fetch to skip. Its drawing stays under its own control either
    way, through the Layers panel (visibility, never computation) rather than
    this switch (computation, never visibility).
    """
    if registry.has("profile"):
        return True
    return registry.has("session_stats") and (session_profile_mode or "off") != "off"


def _optional(value) -> float | None:
    """NaN on the wire means ABSENT. Never let it become a number downstream."""
    return None if value is None or math.isnan(value) else float(value)


_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def step_seconds(timeframe: str) -> int:
    """'15m' -> 900. Bars are close-stamped, so a bar T covers (T - step, T]."""
    return int(timeframe[:-1]) * _UNIT_SECONDS[timeframe[-1]]


def _vap_for(symbol: str, timeframe: str, times) -> list:
    """Each bar's volume-at-price, or None for every bar if the store is absent.

    The store is built from ticks (``python -m src.cli.vap``) and only exists for
    tick-rebuilt symbols. A bar file cannot supply one, and inventing one from the
    bar's high, low and volume would be a fabrication - so None it is, and the
    profile indicator refuses rather than draws a guess.
    """
    step = step_seconds(timeframe)
    base = step_seconds(profile_cfg.BASE_TIMEFRAME)
    if step < base or step % base:
        # The store holds one row per BASE bar. A 15s bar asking it for 15
        # seconds gets whatever 30s bars happen to close in that window - none
        # for the first half of every 30s, both halves' volume for the second.
        # Neither is that bar's volume at price, and the store cannot be sliced
        # finer than it was folded. Refuse; the indicator publishes None.
        logger.debug("%s cannot be profiled from a %s store", timeframe,
                     profile_cfg.BASE_TIMEFRAME)
        return [None] * len(times)
    try:
        return [store_vap.histogram(symbol, profile_cfg.BASE_TIMEFRAME, t - step, t)
                for t in times]
    except store_vap.NotBuilt:
        return [None] * len(times)


def bar_events(bars, symbol: str = None, timeframe: str = None,
               with_vap: bool = False) -> list[BarClose]:
    """Structured bar records -> BarClose events, in order.

    Columns are pulled to Python lists once. Reading fields off numpy scalars
    per bar costs several times more than the indicator pass itself.

    ``with_vap`` is off by default because volume at price costs one store lookup
    per bar, and only the profile indicator reads it. Fetching it for every
    request made a 5,000-bar browse window take minutes, and the chart drew
    nothing at all while it waited.
    """
    epochs = bars["time"].astype("int64")
    times = pd.to_datetime(epochs, unit="s", utc=True)
    o, h = bars["open"].tolist(), bars["high"].tolist()
    lo, c, v = bars["low"].tolist(), bars["close"].tolist(), bars["volume"].tolist()
    d = bars["delta"].tolist()
    bv, sv = bars["buy_volume"].tolist(), bars["sell_volume"].tolist()
    tr = bars["trades"].tolist()

    wants = with_vap and symbol and timeframe and profile_cfg.ENABLED
    vaps = _vap_for(symbol, timeframe, epochs.tolist()) if wants else [None] * len(times)

    return [BarClose(ts=t, open=o[i], high=h[i], low=lo[i], close=c[i], volume=v[i],
                     delta=_optional(d[i]), buy_volume=_optional(bv[i]),
                     sell_volume=_optional(sv[i]), trades=_optional(tr[i]),
                     vap=vaps[i])
            for i, t in enumerate(times)]


def drawable() -> set[str]:
    """The mark sources an indicator is currently configured to emit.

    A Layers checkbox for a drawing that is switched off in config would toggle
    nothing - the marks never arrive. So the panel is built from the intersection
    of what the chart offers and what the backend actually draws, and a layer
    turned off in config simply is not offered.
    """
    sources = set()
    if sessions_cfg.ENABLED and sessions_cfg.DRAW_BOUNDARIES:
        sources.add("sessions")
    if absorption_cfg.ENABLED and absorption_cfg.DRAW_MARKERS:
        sources.add("absorption")
    if swing_cfg.ENABLED and swing_cfg.DRAW_MARKERS:
        sources.add("swing")
    if swing_cfg.ENABLED and swing_cfg.DRAW_RAILS:
        sources.add("extremes")
    if legs_cfg.ENABLED and legs_cfg.DRAW:
        sources.add("legs")
    if breaks_cfg.ENABLED and breaks_cfg.DRAW:
        sources.add("breaks")
    if ribbon_cfg.ENABLED and ribbon_cfg.DRAW:
        sources.add("ribbon")
    if regime_cfg.ENABLED and (regime_cfg.DRAW or regime_cfg.DRAW_BANDS):
        sources.add("regime")
    if ma_cfg.ENABLED and ma_cfg.DRAW and ma_cfg.ACTIVE:
        sources.add("ma")
    if session_stats_cfg.ENABLED and session_stats_cfg.DRAW:
        sources.add("session_stats")
    return sources


def _segment(source: str, points: list[tuple], color: str, width: int,
             mark_id: str | None = None, layer: str | None = None,
             at: int | None = None, offsets: tuple | None = None,
             dash: tuple | None = None) -> dict:
    """A polyline in (time, price) space, for the chart to stroke.

    ``time`` is the EARLIEST point, because that is what the replay trim filter
    compares against: a segment whose left end has scrolled out of the buffer
    cannot be drawn, so it should be dropped rather than half-drawn.

    ``id`` marks a shape that is REDRAWN rather than added. Most marks are events
    - a swing happened, a level broke - and accumulate. The provisional rails are
    not events; they are a running state, re-emitted on every bar. Without an id
    a replay would stack one rail per bar forever. With one, the newest replaces
    the last, in the browser and in ``group_marks`` alike.
    """
    # ``offsets`` shifts a point sideways by pixels from the bar it names. Style
    # belongs in Python, and so does a length that only means anything on screen.
    shifts = offsets or (0.0,) * len(points)
    # Almost every caller passes exactly two points (a ribbon/ma line, a leg, a
    # profile level) - millions of them over a 5,000-bar warmup, since the
    # ribbon alone draws 32 lines a bar. min() over a generator was showing up
    # in a profile as real time on a hot path that never needed the general
    # case; `breaks` is the one caller with three, and still gets a correct
    # answer from the fallback.
    if len(points) == 2:
        t0, t1 = points[0][0], points[1][0]
        earliest = t0 if t0 <= t1 else t1
    else:
        earliest = min(t for t, _ in points)
    mark = {
        "kind": "segment",
        "source": source,
        "time": int(earliest),
        "points": [{"time": int(t), "price": float(p), "dx": float(dx)}
                   for (t, p), dx in zip(points, shifts)],
        "color": color,
        "width": width,
    }
    if dash:
        # A dash pattern in CSS pixels. It is what separates a break from a leg
        # at a glance: two shapes in the same two colours, telling them apart by
        # hue alone, is one meaning too many for one pixel.
        mark["dash"] = [float(n) for n in dash]
    if mark_id is not None:
        mark["id"] = mark_id
    if layer is not None:
        # A LAYER is redrawn wholesale: the newest bar's marks for it replace
        # every earlier one. An id alone cannot do that, because a profile emits
        # a different number of bins on every bar and the surplus ids would
        # linger as ghost bars from a range that has since been reset.
        mark["layer"] = layer
        mark["at"] = int(at)
    return mark


def _level(source: str, price: float, color: str, width: int, *,
           title: str, mark_id: str, dashed: bool = False) -> dict:
    """A horizontal price line across the whole pane, labelled on the axis.

    The shape for a reading that is true *now* and has no beginning: the standing
    high, the standing low, the price at which the next swing confirms. Always
    carries an id - a level is state, so a new one replaces the last rather than
    joining it.
    """
    return {
        "kind": "level",
        "source": source,
        "id": mark_id,
        # Levels are timeless, but the replay trim compares `time` on every mark.
        # Zero is older than any bar, so a level is never trimmed away.
        "time": 0,
        "price": float(price),
        "color": color,
        "width": width,
        "title": title,
        "dashed": dashed,
    }


def marks_for(time: int, row: dict, *, is_first: bool = False,
              close: float | None = None,
              prev_time: int | None = None, prev_session: str | None = None) -> list[dict]:
    """The drawings this row produces. One row in, zero or more shapes out.

    ``is_first`` suppresses the boundary on the first row of any window. Every
    indicator starts with empty state, so its first event always reports
    ``session_new`` - a fact about the indicator waking up, not about the market
    opening a session. Drawing it would put a phantom rule at the left edge of
    every window we ever request.

    ``close`` is this bar's close, needed only to land the vertical stroke of a
    break on the price that went through the level. Absent, the break is drawn as
    the horizontal alone.

    ``prev_time``/``prev_session`` are the previous bar's close time and session.
    A session's CLOSE is its last bar - the one before the next session opens - so
    when this row opens a new session, the previous bar closed the old one, and its
    line is drawn there. The caller threads them; absent (the ladder, the first
    step) no close is drawn, which only loses the rule, never the open.
    """
    marks: list[dict] = []
    if is_first:
        return marks

    if sessions_cfg.ENABLED and sessions_cfg.DRAW_BOUNDARIES and row.get("session_new"):
        name = row.get("session")
        if name is not None:      # entering the halt is not a session open
            marks.append({
                "kind": "vline",
                # Every mark names the indicator that made it, so the chart can
                # hide a layer without knowing what the layer means.
                "source": "sessions",
                "time": int(time),
                "label": name,
                "color": sessions_cfg.LINE_COLORS.get(name, "rgba(125,133,144,0.6)"),
                "labelColor": sessions_cfg.LABEL_COLORS.get(name, "rgba(201,209,217,0.9)"),
            })
        # The session that just ended closed on the previous bar. Drawn there, not
        # here, so the NY close lands at 17:00 ET and not at the 18:00 reopen.
        if (sessions_cfg.DRAW_CLOSE and prev_time is not None
                and prev_session is not None):
            marks.append({
                "kind": "vline",
                "source": "sessions",
                "time": int(prev_time),
                "label": f"{prev_session} close",
                "color": sessions_cfg.CLOSE_LINE_COLORS.get(
                    prev_session, "rgba(125,133,144,0.35)"),
                "labelColor": sessions_cfg.CLOSE_LABEL_COLORS.get(
                    prev_session, "rgba(201,209,217,0.7)"),
                "labelY": sessions_cfg.CLOSE_LABEL_Y,
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
            "color": swing_cfg.HIGH_COLOR if is_high else swing_cfg.LOW_COLOR,
            "shape": swing_cfg.HIGH_SHAPE if is_high else swing_cfg.LOW_SHAPE,
            "size": swing_cfg.MARKER_SIZE,
            "text": "",
        })

    if swing_cfg.ENABLED and swing_cfg.DRAW_RAILS and row.get("hunting"):
        # State, not events: a level standing right now has no start, so these
        # are price lines across the pane rather than segments anchored to a bar.
        for side in ("high", "low"):
            price = row.get(f"extreme_{side}")
            if price is None:
                continue
            live = row["hunting"] == side
            marks.append(_level(
                "extremes", price,
                swing_cfg.LIVE_RAIL_COLOR if live else swing_cfg.FROZEN_RAIL_COLOR,
                swing_cfg.RAIL_WIDTH,
                title=side, mark_id=f"rail_{side}",
            ))

        if swing_cfg.DRAW_TRIGGER and row.get("trigger") is not None:
            marks.append(_level(
                "extremes", row["trigger"], swing_cfg.TRIGGER_COLOR,
                swing_cfg.RAIL_WIDTH, title="trigger", mark_id="trigger",
                dashed=True,
            ))

    if legs_cfg.ENABLED and legs_cfg.DRAW and row.get("leg"):
        up = row["leg"] == "up"
        # One straight line from the swing it left to the swing it arrived at.
        # It does not claim price travelled that path - the candles under it say
        # what price did, and the line only names the two ends and the slope
        # between them. The square-cornered staircase claimed less and drew more:
        # a long horizontal run at a price the market had already left.
        marks.append(_segment(
            "legs",
            [(row["leg_from_time"], row["leg_from_price"]),
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
            dash=breaks_cfg.DASH,
        ))

    if (ribbon_cfg.ENABLED and ribbon_cfg.DRAW and prev_time is not None
            and row.get("ribbon") and row.get("ribbon_prev")):
        # One short line per moving average, from where it sat on the previous bar
        # to where it sits now, coloured by which way it went. A line still warming
        # up (or warming up on the previous bar) has a None slot and is skipped -
        # a segment with no start is a line that begins nowhere.
        for now, before in zip(row["ribbon"], row["ribbon_prev"]):
            if now is None or before is None:
                continue
            up = now >= before
            marks.append(_segment(
                "ribbon",
                [(prev_time, before), (int(time), now)],
                ribbon_cfg.UP_COLOR if up else ribbon_cfg.DOWN_COLOR,
                ribbon_cfg.WIDTH,
            ))

    if (ma_cfg.ENABLED and ma_cfg.DRAW and prev_time is not None
            and row.get("ma") and row.get("ma_prev")):
        # One line per config LINE that is ENABLED, each its own fixed colour -
        # unlike ribbon, which colours every segment by its own slope. The
        # row's ma/ma_prev lists and config ACTIVE are the same length, in the
        # same order, by construction: MA.reset() derives its periods from
        # this exact list.
        for (now, before), line in zip(zip(row["ma"], row["ma_prev"]), ma_cfg.ACTIVE):
            if now is None or before is None:
                continue
            marks.append(_segment(
                "ma",
                [(prev_time, before), (int(time), now)],
                line["color"], ma_cfg.WIDTH,
            ))

    if regime_cfg.ENABLED and regime_cfg.DRAW_BANDS:
        # One band per bar, tinted by the regime it closed in. The frontend
        # shades the bar's slot; runs of one regime read as a continuous band.
        # Emitted per bar - not per run - so replay needs no run state and a
        # browse window never starts inside a band it cannot see the head of.
        color = regime_cfg.BAND_COLORS.get(row.get("regime"))
        if color:
            marks.append({
                "kind": "band",
                "source": "regime",
                "time": int(time),
                "color": color,
            })

    if regime_cfg.ENABLED and regime_cfg.DRAW and row.get("regime_new"):
        # A dashed rule where the regime turned, coloured by the regime it turned
        # INTO - the same vline shape the session boundaries use, told apart by a
        # label a notch lower so the two never print on top of each other.
        name = row.get("regime")
        if name is not None:
            marks.append({
                "kind": "vline",
                "source": "regime",
                "time": int(time),
                "label": name,
                "color": regime_cfg.LINE_COLORS.get(name, "rgba(125,133,144,0.6)"),
                "labelColor": regime_cfg.LABEL_COLORS.get(name, "rgba(201,209,217,0.9)"),
                "labelY": regime_cfg.LABEL_Y,
            })

    if profile_cfg.ENABLED and profile_cfg.DRAW and (
            row.get("profile_bins") or row.get("profile_closed")):
        marks.extend(_profile_marks(int(time), row))

    if session_stats_cfg.ENABLED and session_stats_cfg.DRAW and row.get("session_bins"):
        marks.extend(_session_marks(int(time), row))
    return marks


def _histogram(time: int, bins: list, start: int, end: int, *,
               max_px: int, buy_color: str, sell_color: str,
               source: str = "profile", layer: str = "profile",
               bin_height: int = 1) -> list[dict]:
    """One profile's bars, anchored at the right edge of its own range.

    Both ends of a bin name the SAME bar, and the left one is pushed back a
    number of pixels. An interpolated timestamp has no x coordinate - the chart
    looks a time up in the series and finds no bar there - so a bin drawn between
    two moments would never appear at all.

    No new shape is needed: a bin is a segment, and `segments` already exists.
    That is the point of a shape vocabulary.

    ``source``/``layer`` default to "profile" for the developing-range profile,
    but a second profile at a different scope (session_stats' session-wide one)
    must pass its own - two profiles sharing a layer would replace each other
    in `collapse_redrawn`, and sharing a source would make one Layers checkbox
    hide both.
    """
    heaviest = max((v for _, v, _ in bins), default=0) or 1
    marks: list[dict] = []
    for price, volume, buy in bins:
        pixels = max_px * volume / heaviest
        if pixels < 1:
            continue
        # Coloured by who crossed the spread inside the bin: the same green and
        # red as the delta strip, the same measurement against price instead of
        # against time.
        bought_it = buy * 2 >= volume
        marks.append(_segment(
            source, [(end, price), (end, price)],
            buy_color if bought_it else sell_color,
            bin_height, layer=layer, at=time,
            offsets=(-pixels, 0.0),
        ))
    return marks


def _profile_marks(time: int, row: dict) -> list[dict]:
    """The developing profile, and the finished ones behind it.

    Every one of them lives in the same LAYER, replaced wholesale each bar. A
    closed profile drawn as an event would accumulate: a 5,000-bar browse window
    holds about ninety swings, and ninety histograms is nine thousand segments of
    payload for a picture nobody can read. Only the last few are kept.
    """
    marks: list[dict] = []

    if profile_cfg.DRAW_CLOSED:
        for closed in row.get("profile_closed") or []:
            start, end = int(closed["from_time"]), int(closed["to_time"])
            marks.extend(_histogram(time, closed["bins"], start, end,
                                    max_px=profile_cfg.CLOSED_WIDTH_PX,
                                    buy_color=profile_cfg.CLOSED_BUY_COLOR,
                                    sell_color=profile_cfg.CLOSED_SELL_COLOR,
                                    bin_height=profile_cfg.BIN_HEIGHT))
            # A finished profile keeps its own span, so its point of control is
            # drawn against the structure it describes, not against the right edge.
            marks.append(_segment("profile", [(start, closed["poc"]), (end, closed["poc"])],
                                  profile_cfg.CLOSED_POC_COLOR, 1,
                                  layer="profile", at=time))

    if not row.get("profile_bins"):
        return marks

    start, end = int(row["profile_from_time"]), int(row["profile_to_time"])
    marks.extend(_histogram(time, row["profile_bins"], start, end,
                            max_px=profile_cfg.MAX_WIDTH_PX,
                            buy_color=profile_cfg.BUY_COLOR,
                            sell_color=profile_cfg.SELL_COLOR,
                            bin_height=profile_cfg.BIN_HEIGHT))

    for key, color, width in (("profile_val", profile_cfg.VALUE_AREA_COLOR, 1),
                              ("profile_vah", profile_cfg.VALUE_AREA_COLOR, 1),
                              ("profile_poc", profile_cfg.POC_COLOR, profile_cfg.POC_WIDTH)):
        level = row.get(key)
        if level is not None:
            marks.append(_segment("profile", [(start, level), (end, level)],
                                  color, width, layer="profile", at=time))
    return marks


def _session_marks(time: int, row: dict) -> list[dict]:
    """The session's own volume profile so far - anchored open to now.

    One LAYER, replaced wholesale each bar: the bin count changes every bar as
    volume accumulates, exactly `profile`'s own reason for using a layer
    rather than an id. There is nothing to keep "closed" here - a session ends
    when the next one's session_new resets the indicator, and there is no
    later bar to draw the finished shape against.
    """
    marks: list[dict] = []
    start, end = row.get("session_from_time"), row.get("session_to_time")
    if start is None or end is None:
        return marks

    marks.extend(_histogram(time, row["session_bins"], int(start), int(end),
                            max_px=session_stats_cfg.MAX_WIDTH_PX,
                            buy_color=session_stats_cfg.BUY_COLOR,
                            sell_color=session_stats_cfg.SELL_COLOR,
                            source="session_stats", layer="session_stats",
                            bin_height=session_stats_cfg.BIN_HEIGHT))

    for key, color, width in (("session_val", session_stats_cfg.VALUE_AREA_COLOR, 1),
                              ("session_vah", session_stats_cfg.VALUE_AREA_COLOR, 1),
                              ("session_poc", session_stats_cfg.POC_COLOR,
                               session_stats_cfg.POC_WIDTH)):
        level = row.get(key)
        if level is not None:
            marks.append(_segment("session_stats", [(start, level), (end, level)],
                                  color, width, layer="session_stats", at=time))
    return marks


def collapse_redrawn(marks: list[dict]) -> list[dict]:
    """Drop every redraw but the last. Marks without one are events; keep all.

    Two kinds of redraw. A mark with an ``id`` is a single shape re-emitted on
    every bar, one bar longer - the newest wins. A mark with a ``layer`` belongs
    to a group re-emitted wholesale, and only the group from the LAST bar that
    emitted it survives: a profile publishes a different number of bins each bar,
    and matching them by id would leave ghost bins behind from a range that has
    since been reset.
    """
    latest: dict[str, int] = {}
    for mark in marks:
        layer = mark.get("layer")
        if layer is not None:
            latest[layer] = max(latest.get(layer, -1), mark["at"])

    kept: list[dict] = []
    newest: dict[str, dict] = {}
    for mark in marks:
        layer = mark.get("layer")
        if layer is not None:
            if mark["at"] == latest[layer]:
                kept.append(mark)
        elif mark.get("id") is not None:
            newest[mark["id"]] = mark
        else:
            kept.append(mark)
    return kept + list(newest.values())


def group_marks(marks: list[dict]) -> list[dict]:
    """Group flat marks into the overlay specs the frontend renders.

    Markers are grouped by the indicator that produced them, so a spec stays
    named after one job. The frontend concatenates them regardless - it renders
    shapes, not meanings - but a spec called "absorption" that also carried swing
    points would be a lie to the next reader.
    """
    marks = collapse_redrawn(marks)
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

    levels = [m for m in marks if m["kind"] == "level"]
    if levels:
        specs.append({"id": "levels", "kind": "levels", "levels": levels})

    bands = [m for m in marks if m["kind"] == "band"]
    for source in dict.fromkeys(m["source"] for m in bands):
        group = [m for m in bands if m["source"] == source]
        specs.append({"id": source, "kind": "bands", "bands": group})
    return specs


def for_range(symbol: str, timeframe: str, start: int, count: int,
              profile_mode: str | None = None,
              session_profile_mode: str | None = None) -> list[dict]:
    """Overlay specs for bars ``[start, start+count)``. Used by browse mode.

    Indicators are fed only these bars, in order, so nothing in the output can
    depend on a bar after the last one requested.
    """
    bars = store.slice_bars(symbol, timeframe, start, count)
    if len(bars) == 0:
        return []

    registry = build_registry(profile_mode)
    registry.reset()

    marks: list[dict] = []
    events = bar_events(bars, symbol, timeframe,
                       with_vap=wants_vap(registry, session_profile_mode))
    profile = registry.get("profile")
    last = len(bars) - 1

    prev_time: int | None = None
    prev_session: str | None = None
    for i, (bar, event) in enumerate(zip(bars, events)):
        # Only the newest profile is drawn; the rest of the walk is warmup for it.
        if profile is not None:
            profile.quiet = i < last
        row = registry.update(event)
        marks.extend(marks_for(int(bar["time"]), row, is_first=(i == 0),
                               close=float(bar["close"]),
                               prev_time=prev_time, prev_session=prev_session))
        prev_time, prev_session = int(bar["time"]), row.get("session")
    return group_marks(marks)
