"""Pins the MA indicator: a short list of named SMAs, each its own colour.

Two claims carry it. Each line is the exact mean of the last `period` closes
and refuses until it has that many - the same honesty every SMA in this
codebase keeps. And unlike `ribbon`, a line's drawn colour is fixed by its own
config entry, never by its slope.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config.indicators import ma as cfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.ma import MA

START = datetime(2024, 3, 13, 14, 0, tzinfo=timezone.utc)


def bar(i: int, close: float) -> BarClose:
    """A bar at a given close; the MA indicator reads nothing else off it."""
    return BarClose(ts=START + timedelta(minutes=5 * i), open=close, high=close,
                    low=close, close=close, volume=100.0)


@pytest.fixture(autouse=True)
def two_lines(monkeypatch):
    """A 2-period and a 3-period line, one on and one off, so a test can fill by hand."""
    lines = (
        {"period": 2, "enabled": True, "color": "#111111"},
        {"period": 3, "enabled": True, "color": "#222222"},
        {"period": 4, "enabled": False, "color": "#333333"},
    )
    monkeypatch.setattr(cfg, "LINES", lines)
    monkeypatch.setattr(cfg, "ACTIVE", tuple(line for line in lines if line["enabled"]))


# --- the averages -------------------------------------------------------------

def test_a_disabled_line_never_runs():
    """The 4-period line is off; only the two enabled lines are computed."""
    ma = MA()
    row = ma.update(bar(0, 10.0))
    assert len(row["ma"]) == 2


def test_a_line_is_absent_until_it_has_its_period_of_closes():
    ma = MA()
    row = ma.update(bar(0, 10.0))
    assert row["ma"] == [None, None]
    row = ma.update(bar(1, 12.0))
    assert row["ma"][0] == 11.0, "the 2-period line: mean(10, 12)"
    assert row["ma"][1] is None


def test_each_line_is_the_exact_mean_of_the_last_period_closes():
    ma = MA()
    row = None
    for i, c in enumerate([10.0, 12.0, 14.0, 16.0]):
        row = ma.update(bar(i, c))
    assert row["ma"][0] == 15.0, "mean(14, 16)"
    assert row["ma"][1] == 14.0, "mean(12, 14, 16)"


def test_the_window_slides_and_forgets_the_oldest_close():
    ma = MA()
    for i, c in enumerate([10.0, 12.0, 14.0]):
        ma.update(bar(i, c))
    row = ma.update(bar(3, 20.0))     # 2-period line drops the 12
    assert row["ma"][0] == 17.0, "mean(14, 20), not mean(12, 14, 20)"


def test_an_event_with_no_close_is_refused_not_guessed():
    class Trade:
        ts = START
    with pytest.raises(Unavailable):
        MA().update(Trade())


def test_the_previous_bar_values_ride_the_row():
    ma = MA()
    ma.update(bar(0, 10.0))
    first = ma.update(bar(1, 12.0))
    second = ma.update(bar(2, 8.0))
    assert second["ma_prev"] == first["ma"]


# --- the drawing ---------------------------------------------------------------

def _row(now, before):
    return {"ma": list(now), "ma_prev": list(before)}


def test_each_line_is_drawn_in_its_own_configured_colour_not_by_slope():
    from src.chart import overlays

    # Line 0 (period 2) rose, line 1 (period 3) fell - both must still draw in
    # their OWN configured colour, not green-up/red-down like ribbon.
    marks = overlays.marks_for(200, _row([11.0, 9.0], [10.0, 10.0]), prev_time=100)
    assert len(marks) == 2
    assert marks[0]["color"] == cfg.ACTIVE[0]["color"]
    assert marks[1]["color"] == cfg.ACTIVE[1]["color"]


def test_a_line_that_is_absent_on_either_bar_is_not_drawn():
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0, None], [None, 10.0]), prev_time=100)
    assert marks == []


def test_nothing_is_drawn_without_a_previous_bar():
    from src.chart import overlays

    assert overlays.marks_for(200, _row([11.0], [10.0]), prev_time=None) == []


def test_the_lines_group_into_one_ma_spec():
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0, 9.0], [10.0, 10.0]), prev_time=100)
    specs = overlays.group_marks(marks)
    assert len(specs) == 1
    assert specs[0]["id"] == "ma" and specs[0]["kind"] == "segments"
    assert len(specs[0]["segments"]) == 2


def test_the_field_is_published_even_when_the_drawing_is_off(monkeypatch):
    from src.chart import overlays

    monkeypatch.setattr(cfg, "DRAW", False)
    assert overlays.marks_for(200, _row([11.0], [10.0]), prev_time=100) == []
    ma = MA()
    ma.update(bar(0, 10.0))
    assert ma.update(bar(1, 12.0))["ma"][0] == 11.0
