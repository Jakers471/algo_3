"""Pins the ribbon: a fan of simple moving averages, coloured by slope.

Two claims carry the indicator. Each line is the exact mean of the last `period`
closes and refuses until it has that many - so a warming line is absent, never a
partial average standing in for a full one. And each line segment the chart draws
is coloured by the sign of that line's own slope since the previous bar - green
up, red down.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config.indicators import ribbon as cfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.ribbon import Ribbon

START = datetime(2024, 3, 13, 14, 0, tzinfo=timezone.utc)


def bar(i: int, close: float) -> BarClose:
    """A bar at a given close; the ribbon reads nothing else off it."""
    return BarClose(ts=START + timedelta(minutes=5 * i), open=close, high=close,
                    low=close, close=close, volume=100.0)


@pytest.fixture(autouse=True)
def small_fan(monkeypatch):
    """A three-line fan, periods 2/3/4, so a test can fill it by hand."""
    monkeypatch.setattr(cfg, "PERIODS", (2, 3, 4))


# --- the averages ------------------------------------------------------------

def test_a_line_is_absent_until_it_has_its_period_of_closes():
    """A mean of two closes is not a rougher mean of four; it is a different number."""
    rib = Ribbon()
    row = rib.update(bar(0, 10.0))
    assert row["ribbon"] == [None, None, None], "nothing has a full window yet"
    row = rib.update(bar(1, 12.0))
    assert row["ribbon"][0] == 11.0, "the 2-period line: mean(10, 12)"
    assert row["ribbon"][1] is None and row["ribbon"][2] is None


def test_each_line_is_the_exact_mean_of_the_last_period_closes():
    rib = Ribbon()
    closes = [10.0, 12.0, 14.0, 16.0]
    row = None
    for i, c in enumerate(closes):
        row = rib.update(bar(i, c))
    assert row["ribbon"][0] == 15.0, "mean(14, 16)"
    assert row["ribbon"][1] == 14.0, "mean(12, 14, 16)"
    assert row["ribbon"][2] == 13.0, "mean(10, 12, 14, 16)"


def test_the_window_slides_and_forgets_the_oldest_close():
    rib = Ribbon()
    for i, c in enumerate([10.0, 12.0, 14.0]):
        rib.update(bar(i, c))
    row = rib.update(bar(3, 20.0))       # 2-period line drops the 12
    assert row["ribbon"][0] == 17.0, "mean(14, 20), not mean(12, 14, 20)"


def test_an_event_with_no_close_is_refused_not_guessed():
    class Trade:
        ts = START
    with pytest.raises(Unavailable):
        Ribbon().update(Trade())


# --- the previous values, carried for the slope ------------------------------

def test_the_previous_bar_values_ride_the_row():
    """The chart is stateless; the slope of a line must be in a single row."""
    rib = Ribbon()
    rib.update(bar(0, 10.0))
    first = rib.update(bar(1, 12.0))
    second = rib.update(bar(2, 8.0))
    assert second["ribbon_prev"] == first["ribbon"], "this bar's prev is last bar's now"


# --- the drawing -------------------------------------------------------------

def _row(now, before):
    return {"ribbon": list(now), "ribbon_prev": list(before)}


def test_a_rising_line_is_green_and_a_falling_line_is_red():
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0, 9.0], [10.0, 10.0]), prev_time=100)
    assert len(marks) == 2, "one segment per line that has both endpoints"
    assert marks[0]["color"] == cfg.UP_COLOR, "11 > 10 rose"
    assert marks[1]["color"] == cfg.DOWN_COLOR, "9 < 10 fell"


def test_a_segment_runs_from_the_previous_bar_to_this_one():
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0], [10.0]), prev_time=100)
    pts = marks[0]["points"]
    assert (pts[0]["time"], pts[0]["price"]) == (100, 10.0), "from the previous bar"
    assert (pts[1]["time"], pts[1]["price"]) == (200, 11.0), "to this one"


def test_a_line_that_is_absent_on_either_bar_is_not_drawn():
    """A segment with no start begins nowhere; skip it until both ends exist."""
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0, None], [None, 10.0]), prev_time=100)
    assert marks == []


def test_nothing_is_drawn_without_a_previous_bar():
    """The first bar of a window has nothing to slope away from."""
    from src.chart import overlays

    assert overlays.marks_for(200, _row([11.0], [10.0]), prev_time=None) == []


def test_the_lines_group_into_one_ribbon_spec():
    """Thirty-two lines, one Layers checkbox: all share the source `ribbon`."""
    from src.chart import overlays

    marks = overlays.marks_for(200, _row([11.0, 9.0, 12.0], [10.0, 10.0, 10.0]),
                               prev_time=100)
    specs = overlays.group_marks(marks)
    assert len(specs) == 1
    assert specs[0]["id"] == "ribbon" and specs[0]["kind"] == "segments"
    assert len(specs[0]["segments"]) == 3


def test_the_field_is_published_even_when_the_drawing_is_off(monkeypatch):
    """Turning off the drawing must not turn off the numbers behind it."""
    from src.chart import overlays

    monkeypatch.setattr(cfg, "DRAW", False)
    assert overlays.marks_for(200, _row([11.0], [10.0]), prev_time=100) == []
    # The indicator still computes the line.
    rib = Ribbon()
    rib.update(bar(0, 10.0))
    assert rib.update(bar(1, 12.0))["ribbon"][0] == 11.0
