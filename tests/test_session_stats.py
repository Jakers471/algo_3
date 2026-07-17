"""Pins the session scorecard: London/NY only, and every reading it publishes.

Three claims worth protecting. It refuses outside config TRACKED_SESSIONS - a
"session so far" for Asia or the halt is a number nobody asked for. The ratio
fields (net_ratio, closed_ratio) need no range_scale to be regime-invariant -
they are already a fraction of the session's own range. And
session_range/session_net/session_travel are the ONE place besides range_scale
itself that ever touches points, so they must convert through it rather than
publish points directly (tests/test_fields.py enforces the codebase-wide rule).

No body/wick split is pinned here because none is published: given
session_net_ratio and session_closed_ratio, open_ratio = closed_ratio -
net_ratio always, and body/up-wick/low-wick are arithmetic on those two - a
provable redundancy, not a judgment call.
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


@pytest.fixture(autouse=True)
def short_recent_window(monkeypatch):
    """A 2-bar floor so a short test can fill the recent-delta window."""
    monkeypatch.setattr(cfg, "RECENT_MIN_BARS", 2)


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

def test_open_ratio_is_recoverable_from_closed_and_net_ratio_alone():
    """The provable redundancy the wick fields were cut for: open_ratio =
    closed_ratio - net_ratio always, so a body/wick split adds no information."""
    ss = SessionStats()
    ss.update(bar(0, 100, 110, 90, 105), up(new=True))    # session_open = 100
    row = ss.update(bar(1, 105, 110, 90, 96), up())
    open_ratio = row["session_closed_ratio"] - row["session_net_ratio"]
    expected_open_ratio = (100.0 - 90.0) / (110.0 - 90.0)   # (session_open - low) / range
    assert open_ratio == pytest.approx(expected_open_ratio)


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


# --- volume: cumulative and honest; delta: recent, never cumulative -----------

def test_volume_and_delta_are_none_on_a_bar_with_no_order_flow():
    ss = SessionStats()
    row = ss.update(bar(0, 100, 101, 99, 100), up(new=True))
    assert row["session_volume"] is None
    assert row["session_delta_recent"] is None


def test_volume_accumulates_since_the_session_opened():
    """Unsigned and additive - unlike delta, cumulative volume stays honest."""
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100, delta=20.0, volume=200.0), up(new=True))
    row = ss.update(bar(1, 100, 102, 99, 101, delta=-5.0, volume=150.0), up())
    assert row["session_volume"] == 350.0


def test_delta_recent_is_none_until_the_window_has_enough_bars(monkeypatch):
    monkeypatch.setattr(cfg, "RECENT_MIN_BARS", 3)
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100, delta=20.0, volume=200.0), up(new=True))
    row = ss.update(bar(1, 100, 102, 99, 101, delta=-5.0, volume=150.0), up())
    assert row["session_delta_recent"] is None    # only 2 of 3 bars seen


def test_delta_recent_sums_the_window_not_the_whole_session():
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100, delta=20.0, volume=200.0), up(new=True))
    row = ss.update(bar(1, 100, 102, 99, 101, delta=-5.0, volume=150.0), up())
    assert row["session_delta_recent"] == 15.0


def test_delta_recent_ages_out_bars_older_than_the_window(monkeypatch):
    """The whole point: a crash's real selling must not be cancelled by a
    later, unrelated regime once it has scrolled out of the recent window."""
    monkeypatch.setattr(cfg, "RECENT_MIN_BARS", 2)
    monkeypatch.setattr(cfg, "RECENT_WINDOW_MINUTES", 10)   # 2 bars at 5m each
    ss = SessionStats()
    ss.update(bar(0, 100, 101, 99, 100, delta=-500.0, volume=1000.0), up(new=True))
    ss.update(bar(1, 100, 102, 99, 101, delta=-500.0, volume=1000.0), up())
    # Bar 0 is now more than 10 minutes behind bar 2's close; only bars 1-2
    # remain in the window, so the crash's delta must not still be counted.
    row = ss.update(bar(2, 101, 103, 100, 102, delta=300.0, volume=800.0), up())
    assert row["session_delta_recent"] == pytest.approx(-200.0)   # -500 + 300, not -700


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


# --- wants_vap: two independent switches, not one shared ------------------------

class _FakeRegistry:
    """Stands in for a real Registry - only `.has()` is exercised here."""

    def __init__(self, *running):
        self._running = set(running)

    def has(self, indicator_id):
        return indicator_id in self._running


def test_session_profile_alone_wants_vap_without_the_swing_profile():
    """The user's own case: session profile on, swing profile off."""
    from src.chart import overlays

    registry = _FakeRegistry("session_stats")   # profile never built
    assert overlays.wants_vap(registry, session_profile_mode="on")


def test_neither_switch_on_means_no_fetch():
    from src.chart import overlays

    registry = _FakeRegistry("session_stats")
    assert not overlays.wants_vap(registry, session_profile_mode="off")
    assert not overlays.wants_vap(registry, session_profile_mode=None)


def test_the_swing_profile_running_at_all_forces_the_fetch_regardless():
    """If `profile` is already paying for the fetch, session_stats rides along
    for free even with its own switch off - there is no second fetch to skip."""
    from src.chart import overlays

    registry = _FakeRegistry("profile", "session_stats")
    assert overlays.wants_vap(registry, session_profile_mode="off")
