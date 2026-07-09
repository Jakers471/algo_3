"""Pins the structure layer: the adaptive unit, and the swings measured in it.

The load-bearing claim is scale invariance. Multiply every price in the data by
ten and the same swings must be found, because both the threshold and the
retrace scale with the market. If that ever breaks, some number went back to
being denominated in points, and the indicator has quietly become a constant.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config.indicators import range_scale as scale_cfg
from src.config.indicators import swing as swing_cfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.range_scale import RangeScale
from src.indicators.registry import Registry
from src.indicators.swing import Swing

START = datetime(2024, 3, 13, 14, 0, tzinfo=timezone.utc)


def bar(i: int, high: float, low: float) -> BarClose:
    """A bar with a given high/low; open/close sit inside and never matter here."""
    mid = (high + low) / 2
    return BarClose(ts=START + timedelta(minutes=5 * i), open=mid, high=high,
                    low=low, close=mid, volume=100.0)


@pytest.fixture(autouse=True)
def small_window(monkeypatch):
    """Bars are 5 minutes apart, so 30 minutes of memory holds 6 of them."""
    monkeypatch.setattr(scale_cfg, "WINDOW_MINUTES", 30)
    monkeypatch.setattr(scale_cfg, "MIN_BARS", 3)
    monkeypatch.setattr(swing_cfg, "RETRACE", 1.5)


# --- range_scale -------------------------------------------------------------

def test_it_refuses_until_it_has_seen_enough_bars():
    """An estimate from two bars is a different number, not a rougher one."""
    scale = RangeScale()
    for i in range(scale_cfg.MIN_BARS - 1):
        with pytest.raises(Unavailable):
            scale.update(bar(i, 10, 8))
    assert scale.update(bar(9, 10, 8))["range_scale"] == 2.0


def test_the_refused_bars_are_still_remembered():
    """Refusing to publish is not refusing to observe; the window must fill."""
    scale = RangeScale()
    for i, rng in enumerate([1.0, 2.0]):
        with pytest.raises(Unavailable):
            scale.update(bar(i, 10 + rng, 10))
    # Third bar completes MIN_BARS; the median must span all three ranges.
    assert scale.update(bar(2, 13, 10))["range_scale"] == 2.0


def test_it_is_a_median_so_one_violent_bar_does_not_redefine_normal():
    scale = RangeScale()
    ranges = [2.0, 2.0, 2.0, 2.0, 60.0]
    out = None
    for i, rng in enumerate(ranges):
        try:
            out = scale.update(bar(i, 10 + rng, 10))
        except Unavailable:
            pass
    assert out["range_scale"] == 2.0, "the p99 bar must not move the unit"


def test_bars_age_out_by_market_time_not_by_count():
    """The window is minutes. Volatility runs on the clock, not on the bar index."""
    scale = RangeScale()
    for i in range(10):                        # 50 minutes of 2.0-range bars
        try:
            scale.update(bar(i, 12, 10))
        except Unavailable:
            pass
    for i in range(10, 20):                    # 50 more minutes, 8.0-range bars
        out = scale.update(bar(i, 18, 10))
    assert out["range_scale"] == 8.0, "the 30-minute window has forgotten the quiet bars"


def test_a_coarse_timeframe_keeps_min_bars_however_little_time_they_span():
    """Two hours is 240 bars on 30s and two on 1h. A median of two is their mean."""
    scale = RangeScale()
    hourly = [BarClose(ts=START + timedelta(hours=i), open=10, high=12, low=10,
                       close=11, volume=1.0) for i in range(6)]
    out = None
    for b in hourly:                           # each bar is an hour past the window
        try:
            out = scale.update(b)
        except Unavailable:
            out = None
    assert out is not None, "the bar-count floor must survive a window that holds nothing"
    assert len(scale._arrivals) == scale_cfg.MIN_BARS


def test_the_floor_carries_the_ruler_across_a_weekend():
    scale = RangeScale()
    for i in range(6):
        try:
            scale.update(bar(i, 12, 10))
        except Unavailable:
            pass
    monday = BarClose(ts=START + timedelta(days=3), open=10, high=14, low=10,
                      close=12, volume=1.0)
    out = scale.update(monday)
    assert out["range_scale"] is not None, "a gap must not empty the window"


def test_a_dead_tape_has_no_scale_at_all():
    """Zero is not a small unit. A threshold measured in it is zero.

    Real: on 0.21% of tick-built 30s bars, most of the last 60 printed one price.
    Left as 0, swing's threshold becomes 0 and it confirms a structure point on
    almost every bar of a market that is not moving.
    """
    scale = RangeScale()
    out = None
    for i in range(scale_cfg.MIN_BARS + 2):
        try:
            out = scale.update(bar(i, 10, 10))       # high == low, every bar
        except Unavailable:
            out = None
    assert out is None, "a flat window must not publish a scale of zero"


def test_swing_finds_no_structure_on_a_dead_tape():
    """The refusal has to reach the consumer, or it bought nothing."""
    reg = registry()
    rows = [reg.update(bar(i, 10, 10)) for i in range(scale_cfg.MIN_BARS + 5)]
    assert all(r["range_scale"] is None for r in rows)
    assert all(r["swing"] is None for r in rows), "no swings in a market that never moved"


def test_an_event_with_no_high_or_low_is_refused_not_guessed():
    class Trade:
        ts = START
    with pytest.raises(Unavailable):
        RangeScale().update(Trade())


# --- swing -------------------------------------------------------------------

def registry() -> Registry:
    return Registry([RangeScale(), Swing()])


def test_range_scale_runs_before_swing():
    """The dependency is declared, so the toposort must honour it."""
    assert [i.id for i in registry().order] == ["range_scale", "swing"]


def test_swing_is_unavailable_while_the_scale_warms_up():
    """A threshold without a scale would just be a threshold in points."""
    reg = registry()
    row = reg.update(bar(0, 10, 8))
    assert row["range_scale"] is None
    assert row["swing"] is None, "the registry records absent, never a value"


def run(bars) -> list[dict]:
    """Feed bars through the registry; return only the rows that found a swing."""
    reg = registry()
    return [row for b in bars if (row := reg.update(b))["swing"] is not None]


def rising_then_falling():
    """Warm up flat, climb to a clear high, then retrace well past 1.5x scale."""
    bars = [bar(i, 12, 10) for i in range(4)]              # scale settles at 2.0
    bars += [bar(4, 14, 12), bar(5, 20, 18)]               # the high: 20
    bars += [bar(6, 17, 15)]                               # retrace 5 >= 1.5*2
    return bars


def test_a_swing_high_is_confirmed_only_after_the_retrace():
    found = run(rising_then_falling())
    assert len(found) == 1
    assert found[0]["swing"] == "high"
    assert found[0]["swing_price"] == 20


def test_the_swing_names_the_bar_that_made_it_not_the_bar_that_confirmed_it():
    bars = rising_then_falling()
    found = run(bars)
    assert found[0]["swing_time"] == int(bars[5].ts.timestamp()), "the bar whose high was 20"
    assert found[0]["swing_time"] < int(bars[6].ts.timestamp()), "confirmed later"


def test_a_swing_is_never_stamped_in_the_future():
    """No-lookahead, structurally: a confirmed extreme is always at or behind us."""
    reg = registry()
    for b in rising_then_falling() + [bar(7, 12, 8), bar(8, 20, 18), bar(9, 9, 7)]:
        row = reg.update(b)
        if row["swing"] is not None:
            assert row["swing_time"] <= int(b.ts.timestamp())


def test_a_bar_that_extends_the_extreme_cannot_also_confirm_it():
    """A new high is not a reversal, however wide the bar is."""
    bars = [bar(i, 12, 10) for i in range(4)]
    bars += [bar(4, 40, 10)]        # enormous bar, but it makes a NEW high
    assert run(bars) == []


def test_a_retrace_that_falls_short_confirms_nothing():
    bars = [bar(i, 12, 10) for i in range(4)]   # scale 2.0 -> threshold 3.0
    bars += [bar(4, 20, 18), bar(5, 19, 17.5)]  # retrace of 2.5 < 3.0
    assert run(bars) == []


def test_the_threshold_follows_the_scale_up():
    """The same retrace that confirmed in a quiet market must not in a loud one."""
    quiet = [bar(i, 12, 10) for i in range(4)]                 # scale 2.0, thr 3.0
    loud = [bar(i, 20, 10) for i in range(4)]                  # scale 10.0, thr 15.0
    move = [bar(4, 30, 28), bar(5, 26, 24)]                    # retrace of 4
    assert len(run(quiet + move)) == 1, "4 clears a 3.0 threshold"
    assert run(loud + move) == [], "4 does not clear a 15.0 threshold"


# --- the provisional rails ---------------------------------------------------

def all_rows(bars) -> list[dict]:
    reg = registry()
    return [reg.update(b) for b in bars]


def test_both_rails_exist_on_every_bar_once_warm():
    """The complaint that started this: a running market must never draw a blank."""
    rows = [r for r in all_rows(rising_then_falling()) if r["range_scale"] is not None]
    assert rows, "the fixture must get past the warmup"
    for r in rows:
        assert r["extreme_high"] is not None and r["extreme_low"] is not None
        assert r["hunting"] in ("high", "low")
        assert r["extreme_high"] >= r["extreme_low"]


def test_the_live_rail_ratchets_while_price_runs_and_confirms_nothing():
    bars = [bar(i, 12, 10) for i in range(4)]                  # scale 2.0, threshold 3.0
    bars += [bar(4, 14, 12), bar(5, 16, 14), bar(6, 18, 16)]   # a run of higher highs
    rows = all_rows(bars)[-3:]
    assert [r["swing"] for r in rows] == [None, None, None], "a run confirms nothing"
    assert [r["extreme_high"] for r in rows] == [14, 16, 18], "yet the high keeps ratcheting"
    assert all(r["hunting"] == "high" for r in rows)


def test_the_frozen_rail_does_not_move_while_the_other_is_hunted():
    rows = all_rows(rising_then_falling())
    confirmed = next(i for i, r in enumerate(rows) if r["swing"] == "high")
    after = rows[confirmed]
    assert after["extreme_high"] == after["swing_price"] == 20, "the high froze where it turned"
    assert after["hunting"] == "low", "and the roles swapped"


def test_a_confirmation_freezes_the_live_rail_at_the_swing_it_names():
    found = [r for r in all_rows(rising_then_falling()) if r["swing"]]
    assert found[0]["extreme_high"] == found[0]["swing_price"]
    assert found[0]["extreme_high_time"] == found[0]["swing_time"]


def test_retrace_is_never_negative():
    for r in all_rows(rising_then_falling()):
        if r["retrace"] is not None:
            assert r["retrace"] >= 0


def test_retrace_is_dimensionless():
    """Measured in range_scale, so 10x the prices must not move it at all."""
    shape = rising_then_falling()
    scaled = [BarClose(ts=b.ts, open=b.open * 10, high=b.high * 10, low=b.low * 10,
                       close=b.close * 10, volume=b.volume) for b in shape]
    plain = [r["retrace"] for r in all_rows(shape) if r["retrace"] is not None]
    big = [r["retrace"] for r in all_rows(scaled) if r["retrace"] is not None]
    assert plain == big and len(plain) > 2

    # The rails themselves are prices, so they DO scale.
    hi = [r["extreme_high"] for r in all_rows(shape) if r["extreme_high"] is not None]
    hi10 = [r["extreme_high"] for r in all_rows(scaled) if r["extreme_high"] is not None]
    assert [h * 10 for h in hi] == hi10


def rail_row(**extra) -> dict:
    row = {"hunting": "high", "extreme_high": 20.0, "extreme_high_time": 100,
           "extreme_low": 10.0, "extreme_low_time": 50, "trigger": 17.0}
    row.update(extra)
    return row


def test_a_rail_is_a_level_not_a_segment():
    """A level standing right now has no beginning, so it cannot be a segment.

    As a segment it ran from the bar that made the extreme to the current bar.
    While price runs it makes a new high on the current bar, so that segment had
    zero length on 25% of real 15m bars - invisible, in the one case it existed
    for. A price line has no start to degenerate.
    """
    from src.chart import overlays

    marks = overlays.marks_for(200, rail_row())
    assert {m["id"] for m in marks} == {"rail_high", "rail_low", "trigger"}
    assert all(m["kind"] == "level" for m in marks)
    assert all("points" not in m for m in marks)


def test_the_rails_are_redrawn_not_accumulated():
    """A rail is a running state, re-emitted each bar. Ids collapse to the newest."""
    from src.chart import overlays

    first = overlays.marks_for(200, rail_row())
    later = overlays.marks_for(300, rail_row(extreme_high=25.0, trigger=22.0))

    collapsed = {m["id"]: m for m in overlays.collapse_redrawn(first + later)}
    assert len(collapsed) == 3, "three levels, not six"
    assert collapsed["rail_high"]["price"] == 25.0, "the newest reading survives"


def test_a_level_is_never_trimmed_away():
    """The replay trim compares `time`; a timeless level must outlive every bar."""
    from src.chart import overlays
    assert all(m["time"] == 0 for m in overlays.marks_for(200, rail_row()))


def test_the_hunted_rail_is_drawn_brighter_than_the_frozen_one():
    from src.chart import overlays

    marks = {m["id"]: m for m in overlays.marks_for(200, rail_row())}
    assert marks["rail_high"]["color"] == swing_cfg.LIVE_RAIL_COLOR
    assert marks["rail_low"]["color"] == swing_cfg.FROZEN_RAIL_COLOR
    assert marks["trigger"]["dashed"] is True, "nothing has happened there yet"


def test_the_trigger_sits_a_full_retrace_under_a_provisional_high():
    rows = [r for r in all_rows(rising_then_falling()) if r["trigger"] is not None]
    for r in rows:
        gap = abs(r["retrace"])  # unused, but the relationship below is the point
        live = r["extreme_high"] if r["hunting"] == "high" else r["extreme_low"]
        expected = (live - swing_cfg.RETRACE * r["range_scale"]) if r["hunting"] == "high" \
            else (live + swing_cfg.RETRACE * r["range_scale"])
        assert r["trigger"] == pytest.approx(expected)


def test_no_rails_before_a_scale_exists():
    from src.chart import overlays
    assert overlays.marks_for(200, {"hunting": None}) == []


def test_levels_group_into_their_own_spec():
    from src.chart import overlays

    specs = overlays.group_marks(overlays.marks_for(200, rail_row()))
    levels = [s for s in specs if s["kind"] == "levels"]
    assert len(levels) == 1 and len(levels[0]["levels"]) == 3


def test_scale_invariance_the_same_shape_yields_the_same_swings():
    """Multiply every price by 10: identical swings, at identical times.

    This is the whole thesis. Range scales with volatility, the threshold is
    measured in range, so structure is invariant to how loud the market is. If
    this test fails, some number has reverted to being denominated in points.
    """
    shape = rising_then_falling() + [bar(7, 13, 11), bar(8, 22, 20), bar(9, 12, 10)]
    scaled = [BarClose(ts=b.ts, open=b.open * 10, high=b.high * 10,
                       low=b.low * 10, close=b.close * 10, volume=b.volume)
              for b in shape]

    plain, big = run(shape), run(scaled)
    assert [r["swing"] for r in plain] == [r["swing"] for r in big]
    assert [r["swing_time"] for r in plain] == [r["swing_time"] for r in big]
    assert [r["swing_price"] * 10 for r in plain] == [r["swing_price"] for r in big]
    assert len(plain) >= 2, "the fixture must actually produce swings to compare"


# --- drawing -----------------------------------------------------------------

@pytest.fixture
def markers_on(monkeypatch):
    monkeypatch.setattr(swing_cfg, "DRAW_MARKERS", True)


def test_the_marker_lands_on_the_bar_that_made_the_high(markers_on):
    from src.chart import overlays

    row = {"swing": "high", "swing_price": 20.0, "swing_time": 1_700_000_000}
    marks = overlays.marks_for(1_700_000_300, row)   # confirmed 5 minutes later
    assert len(marks) == 1
    assert marks[0]["time"] == 1_700_000_000, "not the confirming bar's time"
    assert marks[0]["position"] == "aboveBar"
    assert marks[0]["shape"] == swing_cfg.HIGH_SHAPE


def test_a_swing_low_is_drawn_below_the_bar(markers_on):
    from src.chart import overlays

    row = {"swing": "low", "swing_price": 8.0, "swing_time": 1_700_000_000}
    marks = overlays.marks_for(1_700_000_300, row)
    assert marks[0]["position"] == "belowBar"
    assert marks[0]["shape"] == swing_cfg.LOW_SHAPE


def test_no_swing_no_marker(markers_on):
    from src.chart import overlays
    assert overlays.marks_for(1_000, {"swing": None}) == []


def test_the_field_is_published_even_when_the_drawing_is_off(monkeypatch):
    """Turning off a drawing must never turn off the data behind it."""
    from src.chart import overlays

    monkeypatch.setattr(swing_cfg, "DRAW_MARKERS", False)
    row = {"swing": "high", "swing_price": 20.0, "swing_time": 1_700_000_000}
    assert overlays.marks_for(1_700_000_300, row) == []
    assert run(rising_then_falling())[0]["swing"] == "high"


def test_swings_group_into_their_own_spec_beside_absorption(markers_on, monkeypatch):
    """Two indicators, two specs. A spec named for one job holds only that job."""
    from src.chart import overlays
    from src.config.indicators import absorption as absorption_cfg

    monkeypatch.setattr(absorption_cfg, "DRAW_MARKERS", True)
    marks = overlays.marks_for(
        1_700_000_300,
        {"absorption": True, "absorption_side": "buy",
         "swing": "high", "swing_price": 20.0, "swing_time": 1_700_000_000},
    )
    specs = overlays.group_marks(marks)
    assert sorted(s["id"] for s in specs) == ["absorption", "swing"]
    assert all(s["kind"] == "markers" for s in specs)
    assert all(len(s["markers"]) == 1 for s in specs)
