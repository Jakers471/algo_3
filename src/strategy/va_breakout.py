"""Value-area breakout in a directional session (ported from volume_profile_algo).

The rule: in a session that is directional so far (|L1 strength| >= bias_str),
when a CONSOLIDATION base has formed on this timeframe and price sits on the entry
side of it, arm a resting stop at the broken value-area edge - stop at the opposite
edge (risk = VA height), target target_r * risk.

Two scales from ONE frame: L1 session bias is resolution-invariant, so both the
bias and the base come from the frame the engine runs (5m fast / 1m faithful).
One-trade-per-base falls out for free: the stop is armed only while price is still
on the entry side, so once it breaks and fills, no re-arm until a NEW base forms.

Compose-only: indicators do the math (sessions/grade/consolidation); this turns
their output into per-signal bracket levels. Its params live here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.indicators.consolidation import current_base
from src.indicators.grade import rolling_consolidation
from src.indicators.sessions import session_strength
from src.strategy.bracket import Direction


@dataclass(frozen=True)
class VaBreakoutParams:
    # detection (define the base series; fix per walk-forward to reuse a cache)
    state_window: int = 25
    e_cut: float = 0.38
    a_cut: float = 0.55
    n_rows: int = 24
    min_len: int = 15
    max_age: int = 40
    # trading (cheap to sweep)
    bias_str: float = 0.3
    target_r: float = 2.0


class VaBreakout:
    def __init__(self, params: VaBreakoutParams | None = None) -> None:
        self.params = params or VaBreakoutParams()

    def entry_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        strength = session_strength(bars)
        is_cons = rolling_consolidation(bars, p.state_window, p.e_cut, p.a_cut, p.n_rows)
        vah, val = current_base(bars, is_cons, p.min_len, p.max_age, p.n_rows)
        close = bars["close"].to_numpy(float)

        n = len(bars)
        direction = np.full(n, None, dtype=object)
        entry = np.full(n, np.nan)
        stop = np.full(n, np.nan)
        target = np.full(n, np.nan)

        have_base = ~np.isnan(vah) & ~np.isnan(val) & (vah > val)
        risk = np.where(have_base, vah - val, np.nan)

        # Bull session + still below the upside edge -> arm a long breakout at VAH.
        bull = have_base & (strength >= p.bias_str) & (close < vah)
        direction[bull] = Direction.LONG
        entry[bull] = vah[bull]
        stop[bull] = val[bull]
        target[bull] = vah[bull] + p.target_r * risk[bull]

        # Bear session + still above the downside edge -> arm a short breakout at VAL.
        bear = have_base & (strength <= -p.bias_str) & (close > val)
        direction[bear] = Direction.SHORT
        entry[bear] = val[bear]
        stop[bear] = vah[bear]
        target[bear] = val[bear] - p.target_r * risk[bear]

        out = pd.DataFrame(index=bars.index)
        out["entry_stop"] = entry
        out["stop_price"] = stop
        out["target_price"] = target
        out["direction"] = direction
        return out
