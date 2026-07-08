"""Per-bar (time-based) volume facts: rvol, delta, vexp.

One job: turn raw per-bar volume into the facts a strategy/monitor reads at each
bar. This is the VERTICAL volume (one number under each candle) - distinct from
the volume PROFILE (volume by price / POC-VAH-VAL), which lives in
volume_profile.py. Pure: OHLCV in, a facts DataFrame out.

  bar   - this bar's traded volume
  up    - close >= open (direction tint)
  rvol  - relative volume: bar / avg(last `window`)   (>1 loud, <1 quiet; a spike)
  delta - net signed volume over `window` (up-bar vol - down-bar vol; buy/sell lean)
  vexp  - volume expansion: avg(last `fast`) / avg(last `window`) (a sustained ramp)

rvol catches a single loud bar; vexp catches a sustained build - a lone spike
lifts rvol but barely nudges vexp, a real acceleration lifts both.
"""

from __future__ import annotations

import pandas as pd

WINDOW = 20   # baseline / slow lookback
FAST = 3      # short-term lookback (vexp numerator)


def volume_facts(bars: pd.DataFrame, window: int = WINDOW, fast: int = FAST) -> pd.DataFrame:
    """OHLCV -> per-bar {bar, up, rvol, delta, vexp}, aligned to ``bars.index``."""
    v = bars["volume"].astype(float)
    up = bars["close"] >= bars["open"]
    slow_avg = v.rolling(window).mean()
    fast_avg = v.rolling(fast).mean()
    signed = v.where(up, -v)
    return pd.DataFrame({
        "bar": v,
        "up": up,
        "rvol": v / slow_avg,
        "delta": signed.rolling(window).sum(),
        "vexp": fast_avg / slow_avg,
    }, index=bars.index)
