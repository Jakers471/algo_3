"""Pin the VA-breakout building blocks: the pruned mask matches grade, session
strength matches grade, base look-ahead is safe, and signals are well-formed."""

import numpy as np
import pandas as pd
from pytest import approx

from src.indicators.consolidation import current_base
from src.indicators.grade import grade, rolling_consolidation
from src.indicators.sessions import session_strength
from src.strategy.bracket import Direction
from src.strategy.va_breakout import VaBreakout, VaBreakoutParams


def _random_bars(n=140, seed=0, start="2020-01-01 08:00", tz="America/Chicago"):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = close + rng.normal(0, 0.2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, n))
    vol = rng.integers(50, 150, n).astype(float)
    idx = pd.date_range(start, periods=n, freq="1min", tz=tz).tz_convert("UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


def test_rolling_consolidation_matches_grade_exactly():
    window = 25
    bars = _random_bars(140)
    mask = rolling_consolidation(bars, window)
    for i in range(window, len(bars)):
        g = grade(bars.iloc[i - window:i + 1])
        assert bool(mask[i]) == (g.state == "CONSOLIDATION")


def test_session_strength_matches_grade():
    # All bars sit in one NY session (Chicago 08:00+), so it's a single instance.
    bars = _random_bars(60, start="2020-01-02 08:00")
    s = session_strength(bars)
    for i in (10, 30, 59):
        assert s[i] == approx(grade(bars.iloc[: i + 1]).strength)


def test_current_base_is_lookahead_safe_and_fresh():
    n = 60
    bars = _random_bars(n)
    is_cons = np.zeros(n, dtype=bool)
    is_cons[10:30] = True  # one run, ends at index 29
    vah, val = current_base(bars, is_cons, min_len=15, max_age=5)
    assert np.all(np.isnan(vah[:30]))          # never offered during/before the run
    assert not np.isnan(vah[30])               # available the bar after it ends (end 29 + 1)
    assert not np.isnan(vah[34])               # still fresh (34 - 29 = 5 = max_age)
    assert np.isnan(vah[35])                   # stale (35 - 29 = 6 > max_age)


def test_entry_signals_are_well_formed():
    bars = _random_bars(300, seed=3)
    out = VaBreakout(VaBreakoutParams(min_len=8, bias_str=0.0)).entry_signals(bars)
    assert list(out.columns) == ["entry_stop", "stop_price", "target_price", "direction"]
    for _, r in out.iterrows():
        if r["direction"] is Direction.LONG:
            assert r["stop_price"] < r["entry_stop"] <= r["target_price"]
        elif r["direction"] is Direction.SHORT:
            assert r["target_price"] <= r["entry_stop"] < r["stop_price"]
