"""The GRADE engine: reduce any run of OHLCV bars to a regime label.

One job: measure a window of bars on two scale-invariant axes -
  efficiency = |net| / travel   (directed progress vs. churn)
  acceptance = 1 - value-area fraction   (fat vs. thin POC)
- and classify the regime. The SAME measurement runs at every scale (a session,
a 90-bar window), which is the point: no layer computes a subset.

Cutoffs are arguments (defaulting to the module constants) so a strategy can tune
or walk-forward-sweep them. Pure: an OHLCV DataFrame in, a Grade out. Ported from
the volume_profile research core; reuses indicators.volume_profile so the profile
is the same math everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.indicators.volume_profile import profile_for, value_area

N_ROWS = 24          # fixed rows per window -> va_frac is comparable across windows
E_CUT = 0.38         # efficiency >= this = directional (progress)
A_CUT = 0.55         # acceptance  >= this = accepted (fat POC)
MIN_BARS = 8         # fewer bars than this -> UNCLEAR
VALUE_AREA_PCT = 0.70


@dataclass
class Grade:
    # direction / strength
    direction: str          # "bull" | "bear" | "flat"
    net: float
    range: float
    strength: float         # net / range (how far it ended, signed)
    # path
    travel: float
    efficiency: float       # |net| / travel (how directly it got there)
    swings: int
    # shape
    body_pct: float
    close_pos: float        # 0 = closed on low, 1 = on high
    up_wick: float
    low_wick: float
    # timing
    t_high: float           # 0 start .. 1 end
    t_low: float
    # volume
    vol: float
    delta: float
    # volume profile
    poc: float
    vah: float
    val: float
    va_frac: float
    poc_loc: float          # where value formed, 0..1 of range
    acceptance: float       # 1 - va_frac
    scale: float | None     # range / atr (None if atr not supplied)
    # regime verdict + collapsed meta-candle (for recursion)
    state: str
    meta: dict


def _classify(eff: float, acc: float, direction: str, ok: bool, e_cut: float, a_cut: float) -> str:
    if not ok:
        return "UNCLEAR"
    dirn = "UP" if direction == "bull" else "DN"
    if eff >= e_cut:
        return ("GRIND " if acc >= a_cut else "IMPULSE ") + dirn
    return "CONSOLIDATION" if acc >= a_cut else "WHIPSAW"


def _profile(highs, lows, vols, n_rows):
    lo, hi = float(lows.min()), float(highs.max())
    rng = (hi - lo) or 1e-9
    rs = rng / n_rows
    binvol = profile_for(highs, lows, vols, lo, rs, n_rows)
    if binvol.sum() <= 0:
        return lo, rs, 0, 0, n_rows - 1
    poc = int(binvol.argmax())
    va_lo, va_hi = value_area(binvol, poc, VALUE_AREA_PCT)
    return lo, rs, poc, va_lo, va_hi


def grade(bars, *, atr: float | None = None, e_cut: float = E_CUT,
          a_cut: float = A_CUT, min_bars: int = MIN_BARS, n_rows: int = N_ROWS) -> Grade:
    """OHLCV DataFrame (>=1 row) -> Grade. `atr` only feeds the `scale` field."""
    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    v = bars["volume"].to_numpy(float)
    n = len(c)

    O, C, H, L = float(o[0]), float(c[-1]), float(h.max()), float(l.min())
    rng = (H - L) or 1e-9
    net = C - O
    diffs = np.diff(c)
    travel = float(np.abs(diffs).sum()) or 1e-9
    signs = np.sign(diffs)
    signs = signs[signs != 0]
    swings = int((np.diff(signs) != 0).sum()) if len(signs) > 1 else 0

    base, rs, poc_i, va_lo, va_hi = _profile(h, l, v, n_rows)
    poc = base + (poc_i + 0.5) * rs
    vah = base + (va_hi + 1) * rs
    val = base + va_lo * rs
    va_frac = (va_hi - va_lo + 1) / n_rows
    acceptance = 1 - va_frac

    direction = "bull" if net > 0 else "bear" if net < 0 else "flat"
    efficiency = abs(net) / travel
    state = _classify(efficiency, acceptance, direction, n >= min_bars, e_cut, a_cut)

    return Grade(
        direction=direction, net=net, range=rng, strength=net / rng,
        travel=travel, efficiency=efficiency, swings=swings,
        body_pct=abs(net) / rng, close_pos=(C - L) / rng,
        up_wick=(H - max(O, C)) / rng, low_wick=(min(O, C) - L) / rng,
        t_high=int(h.argmax()) / n, t_low=int(l.argmin()) / n,
        vol=float(v.sum()), delta=float(v[c >= o].sum() - v[c < o].sum()),
        poc=poc, vah=vah, val=val, va_frac=va_frac, poc_loc=(poc - L) / rng,
        acceptance=acceptance, scale=(rng / atr if atr else None),
        state=state, meta={"open": O, "high": H, "low": L, "close": C, "volume": float(v.sum())},
    )


def rolling_state(bars, window: int = 25, e_cut: float = E_CUT,
                  a_cut: float = A_CUT, n_rows: int = N_ROWS):
    """Per-bar full regime label = grade(trailing window+1 bars).state.

    Returns an object array of "CONSOLIDATION" | "GRIND UP/DN" | "IMPULSE UP/DN" |
    "WHIPSAW" | "UNCLEAR" (the warmup bars). Unlike rolling_consolidation this is
    NOT pruned - GRIND vs IMPULSE needs the profile on directional bars too, so
    every window is profiled. Matches grade() exactly.
    """
    import numpy as _np

    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    v = bars["volume"].to_numpy(float)
    n = len(c)
    out = _np.array(["UNCLEAR"] * n, dtype=object)
    if n <= window:
        return out

    absdiff = _np.abs(_np.diff(c, prepend=c[0]))
    travel = _np.convolve(absdiff, _np.ones(window), "full")[:n]
    travel = _np.where(travel > 0, travel, 1e-9)
    net = c - _np.concatenate([_np.full(window, _np.nan), o[:-window]])
    eff = _np.abs(net) / travel

    for i in range(window, n):
        a = i - window
        hs, ls, vs = h[a:i + 1], l[a:i + 1], v[a:i + 1]
        lo, hi = float(ls.min()), float(hs.max())
        rng = (hi - lo) or 1e-9
        binvol = profile_for(hs, ls, vs, lo, rng / n_rows, n_rows)
        if binvol.sum() <= 0:
            acc = 0.0
        else:
            va_lo, va_hi = value_area(binvol, int(binvol.argmax()), VALUE_AREA_PCT)
            acc = 1 - (va_hi - va_lo + 1) / n_rows
        ni = net[i]
        direction = "bull" if ni > 0 else "bear" if ni < 0 else "flat"
        out[i] = _classify(eff[i], acc, direction, True, e_cut, a_cut)
    return out


def rolling_consolidation(bars, window: int = 25, e_cut: float = E_CUT,
                          a_cut: float = A_CUT, n_rows: int = N_ROWS):
    """Per-bar boolean: is bar i's trailing (window+1)-bar window a CONSOLIDATION?

    Matches ``grade(...).state == "CONSOLIDATION"`` exactly (efficiency < e_cut AND
    acceptance >= a_cut), but pruned: efficiency is vectorized, and the expensive
    per-window volume profile is computed ONLY where efficiency already qualifies.
    """
    import numpy as _np

    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    v = bars["volume"].to_numpy(float)
    n = len(c)
    out = _np.zeros(n, dtype=bool)
    if n <= window:
        return out

    # Vectorized efficiency over the (window+1)-bar window ending at i.
    absdiff = _np.abs(_np.diff(c, prepend=c[0]))
    travel = _np.convolve(absdiff, _np.ones(window), "full")[:n]  # sum of last `window` diffs
    travel = _np.where(travel > 0, travel, 1e-9)
    net = c - _np.concatenate([_np.full(window, _np.nan), o[:-window]])  # c[i] - o[i-window]
    eff = _np.abs(net) / travel

    acc_cut = 1 - a_cut
    for i in range(window, n):
        if not (eff[i] < e_cut):  # NaN or >= cut -> can't be CONSOLIDATION
            continue
        a = i - window
        hs, ls, vs = h[a:i + 1], l[a:i + 1], v[a:i + 1]
        lo, hi = float(ls.min()), float(hs.max())
        rng = (hi - lo) or 1e-9
        binvol = profile_for(hs, ls, vs, lo, rng / n_rows, n_rows)
        if binvol.sum() <= 0:
            continue
        va_lo, va_hi = value_area(binvol, int(binvol.argmax()), VALUE_AREA_PCT)
        if (va_hi - va_lo + 1) <= acc_cut * n_rows:  # va_frac <= 1 - a_cut  ->  acceptance >= a_cut
            out[i] = True
    return out
