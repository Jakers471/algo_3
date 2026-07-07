"""Donchian breakout - a minimal starter strategy (long or short).

One job: emit a per-bar stop-entry signal. Long = buy-stop at the highest high
of the last ``lookback`` bars; short = sell-stop at the lowest low. When flat,
the engine arms that resting stop; a break through it triggers a bracket with
fixed point-based stop and target.

This is a plumbing-grade starter to exercise the engine, not a tuned edge. Its
parameters live here (with the strategy), not in central config.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategy.bracket import Direction


@dataclass(frozen=True)
class BreakoutParams:
    lookback: int = 20
    stop_points: float = 20.0
    target_points: float = 40.0
    direction: str = "long"  # "long" (buy-stop at rolling high) or "short" (sell-stop at rolling low)


class DonchianBreakout:
    """Breakout: a stop entry at the rolling high (long) or low (short)."""

    def __init__(self, params: BreakoutParams | None = None) -> None:
        self.params = params or BreakoutParams()
        d = self.params.direction.lower()
        if d not in ("long", "short"):
            raise ValueError(f"direction must be 'long' or 'short', got {self.params.direction!r}")
        self.direction = Direction.LONG if d == "long" else Direction.SHORT

    def entry_signals(self, bars: pd.DataFrame) -> pd.DataFrame:
        """Per-bar entry intent: an ``entry_stop`` level and its ``direction``.

        Uses only bars up to and including i (no look-ahead); the level is armed
        at bar i's close and can trigger from bar i+1 onward. ``direction`` is
        None where there is no signal (the warmup bars before ``lookback``).
        """
        lb = self.params.lookback
        if self.direction is Direction.LONG:
            level = bars["high"].rolling(lb).max()
        else:
            level = bars["low"].rolling(lb).min()

        out = pd.DataFrame(index=bars.index)
        out["entry_stop"] = level
        out["direction"] = self.direction
        out.loc[level.isna(), "direction"] = None
        return out
