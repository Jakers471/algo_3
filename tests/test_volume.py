"""Pin the volume facts: rvol spike, signed delta, vexp ramp."""

import pandas as pd
from pytest import approx

from src.indicators.volume import volume_facts


def _bars(vols, ups):
    n = len(vols)
    opens = [100.0] * n
    closes = [101.0 if u else 99.0 for u in ups]  # up = close >= open
    idx = pd.date_range("2020-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": opens, "high": [102.0] * n, "low": [98.0] * n,
                         "close": closes, "volume": vols}, index=idx)


def test_rvol_flags_a_spike():
    vols = [100.0] * 19 + [300.0]      # last bar 3x the 20-bar average
    f = volume_facts(_bars(vols, [True] * 20), window=20)
    assert f["rvol"].iloc[-1] == approx(300.0 / (sum(vols) / 20))
    assert f["rvol"].iloc[-1] > 1.0


def test_delta_is_signed_by_direction():
    # 20 bars: 15 up @100, 5 down @100 -> delta = 15*100 - 5*100 = 1000.
    ups = [True] * 15 + [False] * 5
    f = volume_facts(_bars([100.0] * 20, ups), window=20)
    assert f["delta"].iloc[-1] == approx(1000.0)


def test_vexp_rises_on_a_sustained_ramp():
    vols = [100.0] * 17 + [300.0, 300.0, 300.0]   # last 3 elevated
    f = volume_facts(_bars(vols, [True] * 20), window=20, fast=3)
    assert f["vexp"].iloc[-1] > 1.5   # fast avg well above slow avg
