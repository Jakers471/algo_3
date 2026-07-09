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
    """Warm up in 3 bars, not 30, so a test can be read in one screen."""
    monkeypatch.setattr(scale_cfg, "WINDOW", 6)
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


def test_old_bars_age_out_of_the_window():
    scale = RangeScale()
    for i in range(scale_cfg.WINDOW):          # window full of 2.0-range bars
        try:
            scale.update(bar(i, 12, 10))
        except Unavailable:
            pass
    for i in range(scale_cfg.WINDOW):          # push them all out with 8.0s
        out = scale.update(bar(100 + i, 18, 10))
    assert out["range_scale"] == 8.0


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
