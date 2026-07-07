"""Pin the volume-profile core: overlap-weighted rows and value-area expansion."""

import numpy as np
from pytest import approx

from src.indicators.volume_profile import profile_for, value_area


def test_zero_range_bar_dumps_into_one_row():
    # One flat bar at price 2.5 on a grid of unit rows from base 0 -> row index 2.
    binvol = profile_for(highs=[2.5], lows=[2.5], vols=[10.0], base=0.0, row_size=1.0, n_rows=5)
    assert binvol[2] == approx(10.0)
    assert binvol.sum() == approx(10.0)


def test_overlap_weighting_splits_volume_by_row():
    # A bar spanning [0, 2] with volume 10 covers rows 0 and 1 equally -> 5 each.
    binvol = profile_for(highs=[2.0], lows=[0.0], vols=[10.0], base=0.0, row_size=1.0, n_rows=4)
    assert binvol[0] == approx(5.0)
    assert binvol[1] == approx(5.0)
    assert binvol[2:].sum() == approx(0.0)


def test_poc_is_the_heaviest_row():
    binvol = profile_for(highs=[1.5, 1.5, 3.5], lows=[1.5, 1.5, 3.5],
                         vols=[10.0, 10.0, 1.0], base=0.0, row_size=1.0, n_rows=5)
    assert int(binvol.argmax()) == 1  # two bars at ~1.5 -> row 1 dominates


def test_value_area_expands_to_target_fraction():
    vol = np.array([1.0, 8.0, 1.0])   # POC is the middle, holding 80%
    lo, hi = value_area(vol, poc_idx=1, pct=0.70)
    assert (lo, hi) == (1, 1)         # 80% already >= 70%, no expansion needed
    lo2, hi2 = value_area(vol, poc_idx=1, pct=0.95)
    assert lo2 == 0 and hi2 == 2      # must expand to both neighbors
