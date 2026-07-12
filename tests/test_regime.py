"""Pins the regime read off the ribbon: three dimensionless readings, one label.

The readings must be honest - absent until the fan is fully warm and a scale
exists, a permutation's sortedness for alignment, and a width in range_scale so a
cutoff survives a change of volatility. The label must not chatter: a new regime
holds CONFIRM_BARS bars before it is adopted.
"""

from __future__ import annotations

import pytest

from src.config.indicators import regime as cfg
from src.indicators.base import Unavailable
from src.indicators.regime import Regime


def feed(rib, prev, scale):
    """Drive the indicator with one bar's upstream fields."""
    reg = Regime()
    return reg.update(None, {"ribbon": rib, "ribbon_prev": prev, "range_scale": scale})


# --- honesty -----------------------------------------------------------------

def test_it_refuses_without_a_scale():
    with pytest.raises(Unavailable):
        feed([3.0, 2.0, 1.0], [2.9, 1.9, 0.9], None)


def test_it_refuses_until_every_line_is_warm():
    """A regime read off half a fan is a different number, not a rougher one."""
    with pytest.raises(Unavailable):
        feed([3.0, None, 1.0], [2.9, 1.9, 0.9], 2.0)
    with pytest.raises(Unavailable):
        feed([3.0, 2.0, 1.0], [2.9, None, 0.9], 2.0)


# --- the readings ------------------------------------------------------------

def test_alignment_is_plus_one_for_a_perfectly_stacked_up_fan():
    """Short over long throughout: a clean up-trend, zero inversions."""
    row = feed([5.0, 4.0, 3.0, 2.0], [4.9, 3.9, 2.9, 1.9], 1.0)
    assert row["ribbon_align"] == 1.0


def test_alignment_is_minus_one_for_a_fully_inverted_fan():
    row = feed([2.0, 3.0, 4.0, 5.0], [1.9, 2.9, 3.9, 4.9], 1.0)
    assert row["ribbon_align"] == -1.0


def test_alignment_is_zero_for_a_scrambled_fan():
    """Two up-ordered pairs, two down: the permutation is half sorted."""
    row = feed([1.0, 2.0, 1.5, 0.5, 1.0], [1, 2, 1.5, 0.5, 1.0], 1.0)
    assert -0.6 < row["ribbon_align"] < 0.6


def test_agreement_reads_the_slopes_not_the_positions():
    """All lines higher than last bar: agreement +1, whatever the stacking."""
    row = feed([2.0, 3.0, 4.0], [1.0, 2.0, 3.0], 1.0)
    assert row["ribbon_agree"] == 1.0
    row = feed([2.0, 3.0, 4.0], [9.0, 9.0, 9.0], 1.0)
    assert row["ribbon_agree"] == -1.0


def test_width_is_the_spread_over_range_scale():
    """(max - min) / scale. In range_scale, so ten-x the prices changes nothing."""
    row = feed([5.0, 4.0, 1.0], [5, 4, 1], 2.0)
    assert row["ribbon_width"] == pytest.approx((5.0 - 1.0) / 2.0)


def test_width_is_dimensionless():
    plain = feed([5.0, 4.0, 1.0], [5, 4, 1], 2.0)["ribbon_width"]
    big = feed([50.0, 40.0, 10.0], [50, 40, 10], 20.0)["ribbon_width"]
    assert plain == big


# --- the label ---------------------------------------------------------------

def stacked_up(scale):
    """A wide, perfectly stacked up-fan: an unambiguous up-trend at these cutoffs."""
    lines = [100.0 - i for i in range(8)]          # 100..93, short over long
    prev = [v - 1 for v in lines]
    return lines, prev, scale


def test_a_wide_stacked_fan_is_a_trend():
    lines, prev, _ = stacked_up(1.0)               # width 7 / 1 = 7 >= WIDTH_TREND
    reg = Regime()
    row = {}
    for _ in range(cfg.CONFIRM_BARS + 1):
        row = reg.update(None, {"ribbon": lines, "ribbon_prev": prev, "range_scale": 1.0})
    assert row["regime"] == "up"


def test_a_pinched_fan_is_a_transition_whatever_the_alignment():
    """Below WIDTH_PINCH the fan is a squeeze - a regime loading, not a trend."""
    lines = [100.0 - i * 0.01 for i in range(8)]   # stacked, but width 0.07/1 tiny
    prev = [v - 0.001 for v in lines]
    reg = Regime()
    row = {}
    for _ in range(cfg.CONFIRM_BARS + 1):
        row = reg.update(None, {"ribbon": lines, "ribbon_prev": prev, "range_scale": 1.0})
    assert row["regime"] == "transition"


def test_a_new_regime_must_hold_confirm_bars_before_it_is_adopted():
    """One aberrant bar must not flip the label; chatter is the enemy."""
    up_lines, up_prev, _ = stacked_up(1.0)
    down_lines = [93.0 + i for i in range(8)]       # inverted, wide: a down-trend
    down_prev = [v + 1 for v in down_lines]

    reg = Regime()
    for _ in range(cfg.CONFIRM_BARS + 1):           # settle into "up"
        reg.update(None, {"ribbon": up_lines, "ribbon_prev": up_prev, "range_scale": 1.0})

    # A single down bar: not yet enough to switch.
    row = reg.update(None, {"ribbon": down_lines, "ribbon_prev": down_prev, "range_scale": 1.0})
    assert row["regime"] == "up" and row["regime_new"] is False

    # Hold it CONFIRM_BARS in a row and it is finally adopted, flagged once.
    flips = []
    for _ in range(cfg.CONFIRM_BARS):
        r = reg.update(None, {"ribbon": down_lines, "ribbon_prev": down_prev, "range_scale": 1.0})
        flips.append(r["regime_new"])
    assert reg._regime == "down"
    assert flips.count(True) == 1, "the change is announced exactly once"


def test_the_first_regime_is_not_announced_as_a_change():
    """Establishing the first label is the indicator waking up, not a turn."""
    lines, prev, _ = stacked_up(1.0)
    row = feed(lines, prev, 1.0)
    assert row["regime"] is not None
    assert row["regime_new"] is False


# --- drawing -----------------------------------------------------------------

def test_a_transition_draws_a_vline_coloured_by_the_new_regime():
    from src.chart import overlays

    marks = overlays.marks_for(500, {"regime": "up", "regime_new": True})
    assert len(marks) == 1
    assert marks[0]["kind"] == "vline" and marks[0]["source"] == "regime"
    assert marks[0]["label"] == "up"
    assert marks[0]["color"] == cfg.LINE_COLORS["up"]


def test_no_line_without_a_change():
    from src.chart import overlays
    assert overlays.marks_for(500, {"regime": "up", "regime_new": False}) == []


def test_the_readings_are_published_even_when_the_drawing_is_off(monkeypatch):
    from src.chart import overlays

    monkeypatch.setattr(cfg, "DRAW", False)
    assert overlays.marks_for(500, {"regime": "up", "regime_new": True}) == []
    assert feed([5.0, 4.0, 1.0], [5, 4, 1], 2.0)["ribbon_width"] == 2.0
