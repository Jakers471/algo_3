"""Per-instrument contract specs: tick size, tick value, point value.

One job: expose the traded instruments' specs for sizing and PnL. Values are
read straight from the audit (`config/audit.py`) — the contract specs proven
in DATA_AUDIT.json are the single source of truth; they are not re-typed here.

`point_value` is the dollars-per-point multiplier every position-size and PnL
calculation needs (NQ = $20/pt, ES = $50/pt).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import audit


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    tick_size: float
    tick_value: float
    point_value: float


INSTRUMENTS: dict[str, Instrument] = {
    sym: Instrument(
        symbol=sym,
        name=spec["name"],
        tick_size=spec["tick_size"],
        tick_value=spec["tick_value"],
        point_value=spec["point_value"],
    )
    for sym, spec in audit.CONTRACT_SPECS.items()
}


def get(symbol: str) -> Instrument:
    """Return the Instrument for a symbol (e.g. 'NQ'), or raise if unknown."""
    try:
        return INSTRUMENTS[symbol]
    except KeyError:
        raise KeyError(f"No instrument spec for {symbol!r}; known: {list(INSTRUMENTS)}") from None
