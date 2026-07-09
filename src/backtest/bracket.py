"""The bracket order intent: the contract between strategy and the fill engines.

One job: define what a strategy emits and a fill engine consumes - a resting
stop entry plus its stop-loss and take-profit, as ABSOLUTE price levels. A
strategy computes all three per signal (known at signal time), so risk can vary
trade to trade (e.g. a value-area breakout stops at the opposite VA edge). Levels
are read off the bars in points (audit: back_adjustment - never % or fixed price
assumptions baked into logic). No fill logic here.

This lives with the engine, not with any strategy: the engine and fill models
own the order vocabulary, and strategies plug in by speaking it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Bracket:
    """A resting stop entry with attached stop-loss and take-profit, all absolute.

    ``entry_stop`` is the trigger price; ``stop_price`` / ``target_price`` are the
    protective-stop and take-profit levels. For a long: stop < entry < target;
    for a short: target < entry < stop.
    """

    direction: Direction
    entry_stop: float
    stop_price: float
    target_price: float
