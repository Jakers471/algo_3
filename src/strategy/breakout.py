"""Donchian breakout - a minimal long-only starter strategy.

One job: emit a buy-stop entry level per bar = the highest high of the last
``lookback`` bars. When flat, the engine arms that resting stop; a break above
it triggers a long bracket with fixed point-based stop and target.

This is a plumbing-grade starter to exercise the backtest engine, not a tuned
edge. Its parameters live here (with the strategy), not in central config.
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


class DonchianBreakout:
    """Long-only breakout: buy-stop at the rolling high of the last N bars."""

    direction = Direction.LONG

    def __init__(self, params: BreakoutParams | None = None) -> None:
        self.params = params or BreakoutParams()

    def entry_levels(self, bars: pd.DataFrame) -> pd.Series:
        """Buy-stop trigger per bar: highest high over the last ``lookback`` bars.

        Uses only bars up to and including i (no look-ahead); the level is armed
        at bar i's close and can trigger from bar i+1 onward.
        """
        return bars["high"].rolling(self.params.lookback).max()
