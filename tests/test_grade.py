"""Pin the GRADE engine: the two-axis regime measurement strategies build on.

Synthetic windows with known shapes -> known verdicts: a clean trend is
directional, chop is inefficient, too few bars is UNCLEAR, and the derived
fields (range/net/strength, VA ordering) are correct.
"""

import numpy as np
import pandas as pd
from pytest import approx

from src.indicators.grade import MIN_BARS, grade


def _bars(opens, closes, highs=None, lows=None, vols=None):
    n = len(closes)
    highs = highs if highs is not None else [max(o, c) + 0.1 for o, c in zip(opens, closes)]
    lows = lows if lows is not None else [min(o, c) - 0.1 for o, c in zip(opens, closes)]
    vols = vols if vols is not None else [100.0] * n
    idx = pd.date_range("2020-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows,
                         "close": closes, "volume": vols}, index=idx)


def test_too_few_bars_is_unclear():
    closes = [100 + i for i in range(MIN_BARS - 1)]
    opens = [c - 0.5 for c in closes]
    assert grade(_bars(opens, closes)).state == "UNCLEAR"


def test_clean_uptrend_is_directional_up():
    closes = [100.0 + i for i in range(20)]
    opens = [c - 0.5 for c in closes]
    g = grade(_bars(opens, closes))
    assert g.direction == "bull"
    assert g.efficiency >= 0.38          # monotonic -> high progress
    assert g.state.endswith("UP")        # IMPULSE UP or GRIND UP
    assert g.strength > 0


def test_clean_downtrend_is_directional_down():
    closes = [140.0 - i for i in range(20)]
    opens = [c + 0.5 for c in closes]
    g = grade(_bars(opens, closes))
    assert g.direction == "bear"
    assert g.state.endswith("DN")
    assert g.strength < 0


def test_chop_is_inefficient():
    closes = [100.0 if i % 2 == 0 else 102.0 for i in range(20)]
    opens = [100.0] + closes[:-1]
    g = grade(_bars(opens, closes))
    assert g.efficiency < 0.38           # lots of travel, little net progress
    assert g.swings > 10                 # many direction changes
    assert g.state in ("CONSOLIDATION", "WHIPSAW")


def test_derived_fields_are_correct():
    opens = [100.0] * 10
    closes = [105.0] * 10
    highs = [106.0] * 10
    lows = [99.0] * 10
    g = grade(_bars(opens, closes, highs, lows))
    assert g.range == approx(106.0 - 99.0)          # H - L
    assert g.net == approx(105.0 - 100.0)           # C - O
    assert g.strength == approx(5.0 / 7.0)          # net / range
    assert 0.0 <= g.close_pos <= 1.0
    assert g.val <= g.poc <= g.vah                  # value area brackets the POC


def test_cutoffs_are_tunable():
    # A window that is directional under the default E_CUT but not under a strict one.
    closes = [100.0, 101.0, 100.5, 101.5, 101.0, 102.0, 101.5, 102.5, 102.0, 103.0,
              102.5, 103.5, 103.0, 104.0, 103.5, 104.5, 104.0, 105.0, 104.5, 105.5]
    opens = [100.0] + closes[:-1]
    g_loose = grade(_bars(opens, closes), e_cut=0.0)
    g_strict = grade(_bars(opens, closes), e_cut=0.99)
    assert g_loose.state != "WHIPSAW"                # passes the loose efficiency gate
    assert g_strict.state in ("CONSOLIDATION", "WHIPSAW")  # fails the strict one
