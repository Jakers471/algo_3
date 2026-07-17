"""Pins the structure drawn from swings: the legs, and the levels they break.

Two claims worth protecting. A break fires once - a level that re-broke on every
bar would be a drawing, not an event. And a swing confirmed on a bar can never be
broken by that same bar, because confirmation required price to retrace away from
the extreme; if that ever inverts, every swing would break itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config.indicators import breaks as breaks_cfg
from src.config.indicators import range_scale as scale_cfg
from src.config.indicators import swing as swing_cfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.breaks import Breaks
from src.indicators.legs import Legs
from src.indicators.range_scale import RangeScale
from src.indicators.registry import Registry
from src.indicators.swing import Swing

START = datetime(2024, 3, 13, 14, 0, tzinfo=timezone.utc)


def bar(i: int, high: float, low: float, close: float | None = None) -> BarClose:
    mid = (high + low) / 2
    return BarClose(ts=START + timedelta(minutes=5 * i), open=mid, high=high, low=low,
                    close=mid if close is None else close, volume=100.0)


def at(i: int) -> int:
    return int((START + timedelta(minutes=5 * i)).timestamp())


@pytest.fixture(autouse=True)
def small_window(monkeypatch):
    monkeypatch.setattr(scale_cfg, "WINDOW_MINUTES", 30)
    monkeypatch.setattr(scale_cfg, "MIN_BARS", 3)
    monkeypatch.setattr(swing_cfg, "RETRACE", 1.5)
    monkeypatch.setattr(breaks_cfg, "USE_CLOSE", True)


def registry() -> Registry:
    return Registry([RangeScale(), Swing(), Legs(), Breaks()])


def rows(bars) -> list[dict]:
    reg = registry()
    return [reg.update(b) for b in bars]


# --- ordering ----------------------------------------------------------------

def test_everything_runs_after_what_it_reads():
    order = [i.id for i in registry().order]
    assert order.index("range_scale") < order.index("swing")
    assert order.index("swing") < order.index("legs")
    assert order.index("swing") < order.index("breaks")


# --- legs --------------------------------------------------------------------

def warmup():
    """Four flat bars; range_scale settles at 2.0, so the threshold is 3.0."""
    return [bar(i, 12, 10) for i in range(4)]


def test_one_swing_is_not_a_leg():
    bars = warmup() + [bar(4, 20, 18), bar(5, 16, 14)]     # one swing high at 20
    out = rows(bars)
    assert [r["leg"] for r in out] == [None] * 6
    assert out[-1]["leg_from_price"] is None


def test_absent_before_the_first_swing_is_not_the_same_as_no_leg():
    """Unavailable while nothing could exist; None once it merely did not happen."""
    legs = Legs()
    with pytest.raises(Unavailable):
        legs.update(bar(0, 12, 10), {"swing": None})


def test_two_swings_make_a_leg_that_knows_which_way_it_went():
    bars = warmup()
    bars += [bar(4, 20, 18), bar(5, 16, 14)]      # swing high 20, confirmed at 5
    bars += [bar(6, 15, 8), bar(7, 14, 12)]       # swing low 8, confirmed at 7
    out = rows(bars)

    legs = [r for r in out if r["leg"]]
    assert len(legs) == 1
    leg = legs[0]
    assert leg["leg"] == "down"
    assert (leg["leg_from_price"], leg["leg_to_price"]) == (20, 8)
    assert leg["leg_from_time"] == at(4) and leg["leg_to_time"] == at(6)


# --- breaks ------------------------------------------------------------------

def test_no_level_no_break():
    breaks = Breaks()
    with pytest.raises(Unavailable):
        breaks.update(bar(0, 12, 10), {"swing": None})


def test_the_bar_that_confirms_a_swing_cannot_break_it():
    """Confirmation required a retrace away from the extreme. It is on the wrong side."""
    bars = warmup() + [bar(4, 20, 18), bar(5, 16, 14, close=15)]
    out = rows(bars)
    assert out[-1]["swing"] == "high", "the fixture must actually confirm a swing"
    assert out[-1]["bos"] is None


def test_a_close_above_the_swing_high_is_a_break_up():
    bars = warmup()
    bars += [bar(4, 20, 18), bar(5, 16, 14)]       # swing high 20 confirmed
    bars += [bar(6, 22, 19, close=21)]             # closes above it
    out = rows(bars)
    assert out[-1]["bos"] == "up"
    assert out[-1]["bos_level"] == 20
    assert out[-1]["bos_time"] == at(4), "names the bar that set the level"


def test_a_wick_through_that_closes_back_below_is_not_a_break(monkeypatch):
    bars = warmup()
    bars += [bar(4, 20, 18), bar(5, 16, 14)]
    bars += [bar(6, 22, 15, close=17)]             # pierced 20, closed at 17
    assert rows(bars)[-1]["bos"] is None

    monkeypatch.setattr(breaks_cfg, "USE_CLOSE", False)
    assert rows(bars)[-1]["bos"] == "up", "the wick definition sees it"


def test_a_level_breaks_once_and_is_spent():
    bars = warmup()
    bars += [bar(4, 20, 18), bar(5, 16, 14)]
    bars += [bar(6, 22, 19, close=21), bar(7, 24, 21, close=23)]   # both close above 20
    out = rows(bars)
    assert out[-2]["bos"] == "up"
    assert out[-1]["bos"] is None, "a spent level must not break again every bar"


def test_a_close_below_the_swing_low_is_a_break_down():
    bars = warmup()
    bars += [bar(4, 20, 18), bar(5, 16, 14)]       # swing high 20
    bars += [bar(6, 15, 8), bar(7, 14, 12)]        # swing low 8 confirmed
    bars += [bar(8, 11, 6, close=7)]               # closes below it
    out = rows(bars)
    assert out[-1]["bos"] == "down"
    assert out[-1]["bos_level"] == 8


# --- drawing -----------------------------------------------------------------

def test_a_leg_is_drawn_swing_to_swing_and_solid():
    from src.chart import overlays

    row = {"leg": "up", "leg_from_price": 10.0, "leg_from_time": 100,
           "leg_to_price": 20.0, "leg_to_time": 400}
    seg = overlays.marks_for(400, row)[0]
    assert seg["kind"] == "segment" and seg["source"] == "legs"
    assert [(p["time"], p["price"]) for p in seg["points"]] == [
        (100, 10.0),   # the swing we left
        (400, 20.0),   # the swing we reached. no corner in between
    ]
    # Solid, so the dashed break drawn over it is a different shape and not just
    # a different shade of the same one.
    assert "dash" not in seg


def test_a_break_runs_from_the_level_to_the_close_that_took_it():
    from src.chart import overlays

    row = {"bos": "up", "bos_level": 20.0, "bos_time": 100}
    seg = overlays.marks_for(400, row, close=21.5)[0]
    assert seg["source"] == "breaks"
    assert seg["color"] == breaks_cfg.UP_COLOR
    assert [(p["time"], p["price"]) for p in seg["points"]] == [
        (100, 20.0), (400, 20.0), (400, 21.5)]
    assert seg["dash"] == list(breaks_cfg.DASH)


def test_without_a_close_the_break_is_just_the_level():
    from src.chart import overlays

    row = {"bos": "down", "bos_level": 8.0, "bos_time": 100}
    seg = overlays.marks_for(400, row)[0]
    assert len(seg["points"]) == 2
    assert seg["color"] == breaks_cfg.DOWN_COLOR


def test_a_segment_is_stamped_with_its_earliest_point():
    """The replay trim drops a segment once its left end scrolls out of the buffer."""
    from src.chart import overlays

    row = {"bos": "up", "bos_level": 20.0, "bos_time": 100}
    assert overlays.marks_for(400, row, close=21.5)[0]["time"] == 100


def test_legs_and_breaks_group_into_their_own_specs():
    from src.chart import overlays

    marks = overlays.marks_for(400, {
        "leg": "up", "leg_from_price": 10.0, "leg_from_time": 100,
        "leg_to_price": 20.0, "leg_to_time": 400,
        "bos": "up", "bos_level": 20.0, "bos_time": 100,
    }, close=21.5)
    specs = overlays.group_marks(marks)
    assert sorted(s["id"] for s in specs) == ["breaks", "legs"]
    assert all(s["kind"] == "segments" for s in specs)


def test_turning_the_drawing_off_leaves_the_field(monkeypatch):
    from src.chart import overlays
    from src.config.indicators import legs as legs_cfg

    monkeypatch.setattr(legs_cfg, "DRAW", False)
    monkeypatch.setattr(breaks_cfg, "DRAW", False)
    row = {"leg": "up", "leg_from_price": 10.0, "leg_from_time": 100,
           "leg_to_price": 20.0, "leg_to_time": 400}
    assert overlays.marks_for(400, row) == []


def test_a_consumer_switches_its_dependency_on():
    """Enabling legs must not leave swing off and blow up the toposort."""
    from src.chart import overlays
    from src.config.indicators import legs as legs_cfg

    ids = [i.id for i in overlays.build_registry().order]
    assert legs_cfg.ENABLED and "swing" in ids and "range_scale" in ids


def test_every_offered_layer_is_a_layer_that_draws():
    """A checkbox for a drawing that is off would toggle marks that never come."""
    from src.chart import api, overlays

    offered = {layer["id"] for layer in api._config()["layers"]}
    assert offered
    assert offered <= overlays.drawable()


def test_every_drawable_layer_names_a_real_mark_source():
    """`drawable()` and the marks must agree, or a checkbox hides nothing."""
    from src.chart import overlays

    row = {"session_new": True, "session": "NY",
           "swing": "high", "swing_time": 100, "swing_price": 5.0,
           "leg": "up", "leg_from_time": 90, "leg_from_price": 1.0,
           "leg_to_time": 100, "leg_to_price": 5.0,
           "bos": "up", "bos_level": 4.0, "bos_time": 90,
           "hunting": "high", "extreme_high": 5.0, "extreme_low": 1.0, "trigger": 2.0,
           "ribbon": [5.0], "ribbon_prev": [4.0],
           "regime": "up", "regime_new": True,
           "ma": [5.0], "ma_prev": [4.0]}
    # A previous bar is needed for the ribbon's slope and the session close.
    kw = {"close": 4.5, "prev_time": 90, "prev_session": "NY"}
    sources = {m["source"] for m in overlays.marks_for(100, row, **kw)}
    assert overlays.drawable() <= sources | {"absorption"}
    # Every mark carries a source, including the session rules - the browser
    # filters on it and cannot ask what a mark means.
    assert all(m.get("source") for m in overlays.marks_for(100, row, **kw))
