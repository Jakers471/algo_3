"""Pins the session scorecard: London/NY only, and every reading it publishes.

Three claims worth protecting. It refuses outside config TRACKED_SESSIONS - a
"session so far" for Asia or the halt is a number nobody asked for. The ratio
fields (net_ratio, closed_ratio, body/wick) need no range_scale to be
regime-invariant - they are already a fraction of the session's own range. And
session_range/session_net/session_travel are the ONE place besides range_scale
itself that ever touches points, so they must convert through it rather than
publish points directly (tests/test_fields.py enforces the codebase-wide rule).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from src.config.indicators import session_stats as cfg
from src.events.types import BarClose
from src.indicators.session_stats import SessionStats

START = dt.datetime(2024, 3, 13, 8, 1, tzinfo=dt.timezone.utc)   # inside NY


def bar(i, o, h, lo, c, *, delta=None, volume=100.0, vap=None):
    return BarClose(ts=START + dt.timedelta(minutes=5 * i), open=o, high=h, low=lo,
                    close=c, volume=volume, delta=delta, vap=vap)


def up(session="NY", new=False, scale=10.0):
    return {"session": session, "session_new": new, "range_scale": scale}


# --- scope: London/NY only ----------------------------------------------------

def test_it_refuses_outside_tracked_sessions():
    ss = SessionStats()
    row = ss.update(bar(0, 10, 11, 9, 10), up(session="Asia", new=True))
    assert row["session_bars"] is None
    assert row["session_range"] is None


def test_it_tracks_a_tracked_session():
    ss = SessionStats()
    row = ss.update(bar(0, 10, 11, 9, 10), up(session="London", new=True))
    assert row["session_bars"] == 1


def test_a_session_switch_resets_the_accumulator():
    ss = SessionStats()
    ss.update(bar(0, 10, 15, 9, 14), up(session="NY", new=True))
    ss.update(bar(1, 14, 16, 13, 15), up(session="NY", new=False))
    row = ss.update(bar(2, 20, 21, 19, 20), up(session="NY", new=True))
    assert row["session_bars"] == 1, "a fresh session_new starts over, even same name"


# --- range / net, converted through range_scale, never raw points -------------

def test_range_and_net_are_multiples_of_range_scale_not_points():
    ss = SessionStats()
    ss.update(bar(0, 100, 104, 98, 100), up(new=True, scale=2.0))
    row = ss.update(bar(1, 100, 106, 96, 102), up(scale=2.0))
    # range so far: high=106, low=96 -> 10 points / scale 2.0 = 5.0
    assert row["session_range"] == 5.0
    # net: close(102) - open(100) = 2 points / scale 2.0 = 1.0
    assert row["session_net"] == 1.0


def test_range_and_net_are_none_without_a_range_scale_reading():
    ss = SessionStats()
    row = ss.update(bar(0, 100, 104, 98, 100), {"session": "NY", "session_new": True,
                                                "range_scale": None})
    assert row["session_range"] is None
    assert row["session_net"] is None


# --- the ratio fields: dimensionless by construction ---------------------------

def test_body_and_wicks_sum_to_the_whole_range():
    ss = SessionStats()
    row = ss.update(bar(0, 100, 110, 90, 105), up(new=True))
    total = row["session_body_ratio"] + row["session_upwick_ratio"] + row["session_lowwick_ratio"]
    assert total == pytest.approx(1.0)


def test_a_session_that_sold_off_reads_negative_net_ratio():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 80, 90), up(new=True))
    row = ss.update(bar(1, 90, 91, 79, 80), up())
    assert row["session_net_ratio"] < 0


def test_closed_ratio_is_near_zero_at_the_session_low():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 80, 100), up(new=True))
    row = ss.update(bar(1, 100, 101, 79, 79), up())
    assert row["session_closed_ratio"] == pytest.approx(0.0)


# --- travel and efficiency -----------------------------------------------------

def test_travel_accumulates_every_bars_own_range():
    ss = SessionStats()
    ss.update(bar(0, 100, 105, 99, 102), up(new=True, scale=1.0))    # range 6
    row = ss.update(bar(1, 102, 103, 100, 101), up(scale=1.0))       # range 3
    assert row["session_travel"] == 9.0    # (6 + 3) / scale(1.0)


def test_a_straight_line_session_has_efficiency_near_one():
    """No backtrack at all: travel equals range, so efficiency is 1.0."""
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 100, 101), up(new=True))
    row = ss.update(bar(1, 101, 105, 101, 105), up())
    assert row["session_efficiency"] == pytest.approx(1.0)


def test_a_chopping_session_has_efficiency_below_one():
    ss = SessionStats()
    ss.update(bar(0, 100, 110, 90, 100), up(new=True))
    row = ss.update(bar(1, 100, 110, 90, 100), up())    # retraced the whole range
    assert row["session_efficiency"] < 1.0


# --- direction changes: a reversal, not a first move ----------------------------

def test_the_first_move_off_flat_is_not_a_direction_change():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100), up(new=True))
    row = ss.update(bar(1, 100, 102, 100, 101), up())     # first real close move
    assert row["session_dir_changes"] == 0


def test_a_genuine_reversal_is_counted():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100), up(new=True))
    ss.update(bar(1, 100, 102, 100, 101), up())    # up
    row = ss.update(bar(2, 101, 101, 98, 99), up())  # down: a reversal
    assert row["session_dir_changes"] == 1


# --- where the extremes were made -----------------------------------------------

def test_high_at_ratio_reads_early_when_the_high_prints_early():
    ss = SessionStats()
    ss.update(bar(0, 100, 120, 99, 110), up(new=True))    # the session high, bar 1
    ss.update(bar(1, 110, 111, 105, 108), up())
    row = ss.update(bar(2, 108, 109, 104, 106), up())
    assert row["session_high_at_ratio"] == pytest.approx(1 / 3)


# --- volume and delta: absent, never a proxy zero -------------------------------

def test_volume_and_delta_are_none_on_a_bar_with_no_order_flow():
    ss = SessionStats()
    row = ss.update(bar(0, 100, 101, 99, 100), up(new=True))
    assert row["session_volume"] is None
    assert row["session_delta"] is None


def test_volume_and_delta_accumulate_when_order_flow_is_present():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100, delta=20.0, volume=200.0), up(new=True))
    row = ss.update(bar(1, 100, 102, 99, 101, delta=-5.0, volume=150.0), up())
    assert row["session_volume"] == 350.0
    assert row["session_delta"] == 15.0


# --- POC: needs volume at price, refuses (None) without it ----------------------

def _vbar(i, o, h, lo, c, levels):
    prices = np.array([p for p, _, _ in levels])
    vol = np.array([v for _, v, _ in levels], dtype=np.int64)
    buy = np.array([b for _, _, b in levels], dtype=np.int64)
    return bar(i, o, h, lo, c, vap=(prices, vol, buy))


def test_poc_is_none_without_volume_at_price():
    ss = SessionStats()
    row = ss.update(bar(0, 100, 101, 99, 100), up(new=True))
    assert row["session_poc"] is None


def test_poc_is_the_heaviest_traded_price_in_the_session_so_far():
    """The POC is binned by range_scale, so it lands on a bin's LOWER edge, not
    necessarily the exact tick that traded - same convention as store.rebin()."""
    ss = SessionStats()
    ss.update(_vbar(0, 100, 102, 98, 100, [(99.0, 10, 5), (101.0, 90, 40)]), up(new=True))
    row = ss.update(_vbar(1, 100, 103, 97, 101, [(102.0, 5, 5)]), up())
    assert row["session_poc"] == 100.0    # the bin holding the heaviest level, 101.0


def test_val_and_vah_bracket_the_poc():
    ss = SessionStats()
    ss.update(_vbar(0, 100, 102, 98, 100, [(99.0, 10, 5), (101.0, 90, 40)]), up(new=True))
    row = ss.update(_vbar(1, 100, 103, 97, 101, [(102.0, 5, 5)]), up())
    assert row["session_val"] <= row["session_poc"] <= row["session_vah"]


def test_bins_and_span_are_none_without_a_range_scale_reading():
    ss = SessionStats()
    row = ss.update(_vbar(0, 100, 102, 98, 100, [(99.0, 10, 5)]),
                    {"session": "NY", "session_new": True, "range_scale": None})
    assert row["session_bins"] is None
    assert row["session_from_time"] is None


def test_bins_span_from_the_sessions_first_bar_to_its_latest():
    ss = SessionStats()
    ss.update(_vbar(0, 100, 102, 98, 100, [(99.0, 10, 5)]), up(new=True))
    row = ss.update(_vbar(1, 100, 103, 97, 101, [(102.0, 5, 5)]), up())
    assert row["session_from_time"] == int(bar(0, 0, 0, 0, 0).ts.timestamp())
    assert row["session_to_time"] == int(bar(1, 0, 0, 0, 0).ts.timestamp())


# --- the drawing: a session profile must never collide with the swing profile ---

def test_the_session_profile_draws_under_its_own_source_and_layer():
    """Sharing `profile`'s layer would make the two histograms replace each
    other every bar; sharing its source would make one Layers checkbox hide both."""
    from src.chart import overlays

    row = {
        "session_bins": [[100.0, 10, 5], [101.0, 20, 15]],
        "session_from_time": 100, "session_to_time": 200,
        "session_poc": 101.0, "session_val": 100.0, "session_vah": 101.0,
    }
    marks = overlays.marks_for(200, row)
    sources = {m["source"] for m in marks}
    assert sources == {"session_stats"}
    layers = {m.get("layer") for m in marks}
    assert layers == {"session_stats"}


def test_tracked_sessions_config_is_london_and_ny():
    """The scope this whole indicator exists to enforce."""
    assert set(cfg.TRACKED_SESSIONS) == {"London", "NY"}
