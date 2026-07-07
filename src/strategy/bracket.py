"""The bracket order intent: the contract between strategy and the fill engines.

One job: define what a strategy emits and a fill engine consumes - a resting
stop entry plus its stop-loss and take-profit, expressed in POINT offsets
(audit: back_adjustment - never absolute price or %). No fill logic here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Bracket:
    """A resting stop entry with attached stop-loss and take-profit.

    ``entry_stop`` is an absolute trigger price (read off the bars).
    ``stop_offset`` / ``target_offset`` are POINT distances from the fill.
    """

    direction: Direction
    entry_stop: float
    stop_offset: float
    target_offset: float

    def stop_price(self, entry_fill: float) -> float:
        """Protective-stop price given the actual entry fill."""
        if self.direction is Direction.LONG:
            return entry_fill - self.stop_offset
        return entry_fill + self.stop_offset

    def target_price(self, entry_fill: float) -> float:
        """Take-profit price given the actual entry fill."""
        if self.direction is Direction.LONG:
            return entry_fill + self.target_offset
        return entry_fill - self.target_offset
