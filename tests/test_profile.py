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


