"""Pins volume at price: the value area, and the store that feeds it.

The invariant that matters most is not here - it is in `python -m src.cli.vap
--verify`, which checks that every bar's histogram sums to that bar's own volume
against the bar file. Losing or double-counting a single contract would make
every profile quietly wrong, and no picture would ever show it.

What is here: the value area is a CONTIGUOUS band grown from the point of
control, never the highest-volume levels swept up until 70% is reached - that
would be a list of prices with holes in it, and VAH and VAL would name levels
nobody can trade against.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.config import profile as cfg
from src.profile import store
from src.profile.build import IDX_DTYPE, VAP_DTYPE
from src.profile.value_area import EmptyProfile, value_area


def prof(*volumes, start=100.0, step=0.25):
    prices = start + step * np.arange(len(volumes))
    return prices, np.array(volumes, dtype=np.int64)


# --- the value area ----------------------------------------------------------

def test_the_point_of_control_is_where_most_volume_traded():
    prices, volumes = prof(1, 2, 9, 2, 1)
    poc, _, _ = value_area(prices, volumes)
    assert poc == prices[2]


def test_the_band_is_contiguous_even_when_a_far_level_is_heavy():
    """A lone spike at the edge must not join the value area by teleporting."""
    prices, volumes = prof(50, 1, 1, 90, 1, 1, 50)
    poc, val, vah = value_area(prices, volumes, coverage=0.60)
    assert poc == prices[3]
    assert val <= poc <= vah
    # Everything between VAL and VAH is inside; nothing outside was counted.
    inside = np.flatnonzero((prices >= val) & (prices <= vah))
    assert len(inside) == inside[-1] - inside[0] + 1, "no holes"


def test_it_grows_towards_the_heavier_side():
    prices, volumes = prof(1, 1, 10, 8, 1)
    poc, val, vah = value_area(prices, volumes, coverage=0.85)
    assert poc == prices[2]
    assert vah == prices[3], "the 8 above beat the 1 below"


def test_it_covers_at_least_the_requested_share():
    prices, volumes = prof(5, 10, 30, 10, 5)
    _, val, vah = value_area(prices, volumes, coverage=0.70)
    inside = volumes[(prices >= val) & (prices <= vah)].sum()
    assert inside / volumes.sum() >= 0.70


def test_it_stops_at_the_edge_rather_than_running_off_it():
    prices, volumes = prof(1, 1, 50)          # POC is the topmost level
    poc, val, vah = value_area(prices, volumes, coverage=0.99)
    assert vah == prices[-1] and val == prices[0]


def test_a_tie_for_the_point_of_control_picks_the_middle_not_the_first():
    """Deterministic, and never an edge just because it was scanned first."""
    prices, volumes = prof(9, 1, 9, 1, 9)
    poc, _, _ = value_area(prices, volumes)
    assert poc == prices[2]


def test_no_volume_is_not_a_profile():
    prices, volumes = prof(0, 0, 0)
    with pytest.raises(EmptyProfile):
        value_area(prices, volumes)


# --- folding one-tick levels into wider bins ---------------------------------

def test_rebin_is_an_exact_fold():
    prices = np.array([100.0, 100.25, 100.5, 100.75, 101.0])
    volume = np.array([1, 2, 3, 4, 5], dtype=np.int64)
    buy = np.array([1, 1, 1, 1, 1], dtype=np.int64)

    p, v, b = store.rebin(prices, volume, buy, bin_size=1.0)
    assert list(p) == [100.0, 101.0]
    assert list(v) == [10, 5], "no contract is created or lost by binning"
    assert v.sum() == volume.sum() and b.sum() == buy.sum()


def test_rebin_below_one_tick_changes_nothing():
    prices, volume = prof(1, 2, 3)
    buy = volume // 2
    p, v, b = store.rebin(prices, volume, buy, bin_size=cfg.TICK_SIZE)
    assert np.array_equal(p, prices) and np.array_equal(v, volume)


# --- the packed store --------------------------------------------------------

@pytest.fixture
def packed(tmp_path, monkeypatch):
    """Two bars: one at t=60 with levels 100/101, one at t=120 with 101/102."""
    levels = np.array([(400, 10, 6), (404, 20, 5),        # bar at 60
                       (404, 30, 10), (408, 40, 40)],     # bar at 120
                      dtype=VAP_DTYPE)
    index = np.array([(60, 0, 2), (120, 2, 2)], dtype=IDX_DTYPE)
    (tmp_path / "T_30s.vap").write_bytes(levels.tobytes())
    (tmp_path / "T_30s.idx").write_bytes(index.tobytes())
    monkeypatch.setattr(cfg, "CACHE_DIR", tmp_path)
    store._CACHE.clear()
    yield
    store._CACHE.clear()


def test_a_range_folds_a_price_traded_in_several_bars(packed):
    prices, volume, buy = store.histogram("T", "30s", 0, 120)
    assert list(prices) == [100.0, 101.0, 102.0]
    assert list(volume) == [10, 50, 40], "101 traded in both bars and is summed once"
    assert list(buy) == [6, 15, 40]


def test_the_range_is_left_open_because_bars_are_close_stamped(packed):
    """A bar labelled T covers (T-step, T]. Asking for (60, 120] excludes bar 60."""
    prices, volume, _ = store.histogram("T", "30s", 60, 120)
    assert list(prices) == [101.0, 102.0]
    assert list(volume) == [30, 40]


def test_an_empty_range_is_empty_not_an_error(packed):
    prices, volume, _ = store.histogram("T", "30s", 500, 900)
    assert len(prices) == 0 and volume.sum() == 0


def test_an_unbuilt_store_says_how_to_build_it(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CACHE_DIR", tmp_path)
    store._CACHE.clear()
    with pytest.raises(store.NotBuilt, match="src.cli.vap"):
        store.histogram("MISSING", "30s", 0, 100)


# --- the indicator: three ranges, and it refuses without ticks ---------------

import datetime as _dt

from src.config.indicators import profile as pcfg
from src.events.types import BarClose
from src.indicators.base import Unavailable
from src.indicators.profile import Profile

_START = _dt.datetime(2024, 3, 13, 14, 0, tzinfo=_dt.timezone.utc)


def vbar(i, close=100.0, levels=((100.0, 10, 5),)):
    prices = np.array([p for p, _, _ in levels])
    vol = np.array([v for _, v, _ in levels], dtype=np.int64)
    buy = np.array([b for _, _, b in levels], dtype=np.int64)
    return BarClose(ts=_START + _dt.timedelta(minutes=5 * i), open=close, high=close,
                    low=close, close=close, volume=float(vol.sum()), vap=(prices, vol, buy))


def up(swing=None, price=None, time=None, scale=8.0):
    row = {"range_scale": scale, "swing": swing}
    if swing:
        row["swing_price"] = price
        row["swing_time"] = time
    return row


def test_a_bar_with_no_volume_at_price_is_refused_not_guessed():
    """A bar file knows its total volume and its range. Not where inside it."""
    bare = BarClose(ts=_START, open=1, high=2, low=0, close=1, volume=10)
    with pytest.raises(Unavailable, match="volume at price"):
        Profile("developing").update(bare, up())


def test_without_a_scale_there_is_no_bin_width():
    with pytest.raises(Unavailable, match="range_scale"):
        Profile("developing").update(vbar(0), {"range_scale": None})


def test_an_unknown_mode_is_a_startup_error():
    with pytest.raises(ValueError, match="unknown profile mode"):
        Profile("sideways")


def test_developing_grows_and_resets_at_a_confirmed_swing():
    p = Profile("developing")
    p.update(vbar(0, levels=((100.0, 10, 5),)), up())
    row = p.update(vbar(1, levels=((100.0, 10, 5),)), up())
    assert row["profile_volume"] == 20, "two bars, both inside the range"

    # A swing confirms, naming bar 1 as the bar that made it.
    at = int(vbar(1).ts.timestamp())
    row = p.update(vbar(2, levels=((100.0, 7, 7),)), up("high", 100.0, at))
    assert row["profile_volume"] == 7, "the range restarts after the swing bar"


def test_a_leg_is_frozen_at_the_bar_that_made_the_swing_not_the_one_that_proved_it():
    p = Profile("leg")
    p.update(vbar(0, levels=((100.0, 10, 5),)), up())
    p.update(vbar(1, levels=((100.0, 10, 5),)), up())
    assert p.update(vbar(2, levels=((100.0, 99, 0),)), up())["profile_poc"] is None, \
        "no leg until two swings bound one"

    at = int(vbar(1).ts.timestamp())
    row = p.update(vbar(3, levels=((100.0, 99, 0),)), up("high", 100.0, at))
    assert row["profile_volume"] == 20, "bars 0 and 1 only: bar 2 came after the swing bar"
    assert row["profile_to_time"] == at, "frozen at the bar that MADE it"


def test_the_box_clips_to_the_band_between_two_confirmed_swings():
    """A leg is an interval in time; a box is an interval in price."""
    p = Profile("box")
    t0 = int(vbar(0).ts.timestamp())
    p.update(vbar(0, levels=((100.0, 10, 5),)), up("low", 100.0, t0))

    t1 = int(vbar(1).ts.timestamp())
    p.update(vbar(1, levels=((110.0, 10, 5),)), up("high", 110.0, t1))

    # Price now trades BELOW the confirmed low - inside the leg, outside the box.
    row = p.update(vbar(2, levels=((90.0, 50, 0), (105.0, 10, 5))), up(scale=80.0))
    # Bars are close-stamped, so the box spans (low_bar, now] - the bar that MADE
    # the low belongs to the leg before it. Left: bar 1's 10 at 110, bar 2's 10 at
    # 105. The 50 contracts at 90 traded inside the leg and outside the box.
    assert row["profile_volume"] == 20
    assert row["profile_val"] >= 100.0 and row["profile_vah"] <= 110.0


def test_the_box_needs_two_confirmed_swings_before_it_exists():
    p = Profile("box")
    row = p.update(vbar(0), up("low", 100.0, int(vbar(0).ts.timestamp())))
    assert row["profile_poc"] is None, "one swing is not a band"


def test_bins_are_sized_in_range_scale_not_in_points(monkeypatch):
    monkeypatch.setattr(pcfg, "BINS_PER_SCALE", 1)
    levels = tuple((100.0 + 0.25 * i, 1, 1) for i in range(40))   # spans 10 points

    quiet = Profile("developing").update(vbar(0, levels=levels), up(scale=2.0))
    loud = Profile("developing").update(vbar(0, levels=levels), up(scale=20.0))
    assert len(quiet["profile_bins"]) > len(loud["profile_bins"]), \
        "a loud market gets wider bins, so the histogram's shape stays comparable"


# --- drawing: a bin is a segment, and the layer is redrawn wholesale ---------

def profile_row(bins, poc=100.0):
    return {"profile_bins": bins, "profile_from_time": 1000, "profile_to_time": 2000,
            "profile_poc": poc, "profile_val": 99.0, "profile_vah": 101.0}


def test_a_profile_needs_no_new_chart_shape():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 8], [101.0, 5, 1]]))
    assert all(m["kind"] == "segment" for m in marks)
    assert all(m["layer"] == "profile" for m in marks)


def test_a_bin_is_coloured_by_who_crossed_the_spread():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 9], [101.0, 10, 1]]))
    assert marks[0]["color"] == pcfg.BUY_COLOR
    assert marks[1]["color"] == pcfg.SELL_COLOR


def test_the_heaviest_bin_is_the_longest_and_none_escapes_its_range():
    from src.chart import overlays
    marks = overlays.marks_for(2000, profile_row([[100.0, 10, 5], [101.0, 5, 2]]))
    lengths = [m["points"][1]["time"] - m["points"][0]["time"] for m in marks[:2]]
    assert lengths[0] > lengths[1]
    assert lengths[0] <= (2000 - 1000) * pcfg.MAX_WIDTH + 1


def test_a_layer_is_replaced_wholesale_so_a_shrinking_profile_leaves_no_ghosts():
    from src.chart import overlays

    wide = overlays.marks_for(2000, profile_row([[100.0, 9, 5], [101.0, 9, 5], [102.0, 9, 5]]))
    narrow = overlays.marks_for(3000, profile_row([[100.0, 9, 5]]))
    kept = overlays.collapse_redrawn(wide + narrow)

    assert all(m["at"] == 3000 for m in kept), "only the newest emission survives"
    assert len(kept) == len(narrow), "the wider profile's surplus bins are gone"
