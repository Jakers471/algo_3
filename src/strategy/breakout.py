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
        """Per-bar entry intent: ``direction`` + absolute ``entry_stop`` /
        ``stop_price`` / ``target_price`` levels.

        Uses only bars up to and including i (no look-ahead); the level is armed
        at bar i's close and can trigger from bar i+1 onward. The stop/target are
        fixed point distances from the entry level (this strategy's constant risk);
        other strategies can vary them per signal. ``direction`` is None where there
        is no signal (the warmup bars before ``lookback``).
        """
        lb = self.params.lookback
        sp, tp = self.params.stop_points, self.params.target_points
        if self.direction is Direction.LONG:
            level = bars["high"].rolling(lb).max()
            stop, target = level - sp, level + tp
        else:
            level = bars["low"].rolling(lb).min()
            stop, target = level + sp, level - tp

        out = pd.DataFrame(index=bars.index)
        out["entry_stop"] = level
        out["stop_price"] = stop
        out["target_price"] = target
        out["direction"] = self.direction
        out.loc[level.isna(), "direction"] = None
        return out
