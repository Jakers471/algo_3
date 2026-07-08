"""Session detection: group bars into session instances (Asia / London / NY).

One job: split an OHLCV window into one instance per session per day, using the
CME session windows in config/session.py. This is what bounds a GRADE reading to
the CURRENT session - grading the whole loaded window collapses efficiency toward
0 (always WHIPSAW), so the L1 session bias must be graded on a session, not the
lot. Pure: OHLCV DataFrame in, instances out. Chart rays are a frontend concern.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import session as cfg


def session_names() -> list[str]:
    return [s["name"] for s in cfg.SESSIONS]


def session_instances(df: pd.DataFrame, max_sessions: int | None = None) -> list[dict]:
    """Group bars into session instances (one per session per day).

    Returns the most-recent ``max_sessions`` instances (by start), each:
      ``{session, positions, start_pos, end_pos, hi_pos, hi_price, lo_pos, lo_price}``
    where positions index into the ORIGINAL ``df`` rows.
    """
    if df is None or df.empty:
        return []
    if max_sessions is None:
        max_sessions = cfg.MAX_SESSIONS

    local = df.index.tz_convert(cfg.SESSION_TZ)
    minute = local.hour.to_numpy() * 60 + local.minute.to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)

    # Assign each bar to a session (windows don't overlap -> first match).
    sess = np.full(n, -1, dtype=int)
    for si, s in enumerate(cfg.SESSIONS):
        if s["end"] <= s["start"]:  # wraps past midnight
            mask = (minute >= s["start"]) | (minute < s["end"])
        else:
            mask = (minute >= s["start"]) & (minute < s["end"])
        sess[(sess == -1) & mask] = si

    # Instance day: a wrapping session's after-midnight bars belong to the day it
    # STARTED (the previous calendar day), so they group into one instance.
    anchor = local.normalize().tz_localize(None).to_numpy().copy()
    for si, s in enumerate(cfg.SESSIONS):
        if s["end"] <= s["start"]:
            morning = (sess == si) & (minute < s["end"])
            anchor[morning] -= np.timedelta64(1, "D")

    keep = sess >= 0
    if not keep.any():
        return []

    sub = pd.DataFrame({
        "pos": np.arange(n)[keep],
        "sess": sess[keep],
        "anchor": anchor[keep],
        "high": highs[keep],
        "low": lows[keep],
    })

    insts = []
    for (si, _day), g in sub.groupby(["sess", "anchor"], sort=False):
        hi_i = int(g["high"].values.argmax())
        lo_i = int(g["low"].values.argmin())
        insts.append({
            "session": cfg.SESSIONS[int(si)]["name"],
            "positions": g["pos"].to_numpy(),
            "start_pos": int(g["pos"].iloc[0]),
            "end_pos": int(g["pos"].iloc[-1]),
            "hi_price": float(g["high"].iloc[hi_i]),
            "hi_pos": int(g["pos"].iloc[hi_i]),
            "lo_price": float(g["low"].iloc[lo_i]),
            "lo_pos": int(g["pos"].iloc[lo_i]),
        })

    insts.sort(key=lambda x: x["start_pos"])
    return insts[-max_sessions:]


def latest_session_bars(df: pd.DataFrame) -> pd.DataFrame:
    """The bars of the most recent session instance (falls back to all bars if
    no session has formed) - the window a strategy grades for its L1 bias."""
    insts = session_instances(df)
    if not insts:
        return df
    last = insts[-1]
    return df.iloc[last["start_pos"]:last["end_pos"] + 1]


def session_strength(df: pd.DataFrame) -> np.ndarray:
    """Per-bar session bias = GRADE's strength, computed cheaply and exactly.

    strength[i] = (close[i] - session_open) / (running_high - running_low), reset
    each session. This equals grade(session_so_far).strength but is resolution-
    invariant and vectorized - net and range depend only on the session's first
    open, last close, and extremes, not the bar size. 0 outside any session.
    """
    n = len(df)
    out = np.zeros(n)
    if n == 0:
        return out
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    for it in session_instances(df, max_sessions=n + 1):
        pos = it["positions"]
        runhi = np.maximum.accumulate(h[pos])
        runlo = np.minimum.accumulate(lo[pos])
        rng = runhi - runlo
        s = np.zeros(len(pos))
        np.divide(c[pos] - o[pos[0]], rng, out=s, where=rng > 0)  # 0 where range is 0
        out[pos] = s
    return out
