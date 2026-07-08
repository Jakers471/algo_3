"""Map a strategy name to its class + params class, and build one from a dict.

One job: let a run config reference a strategy by string (e.g. "breakout") and
have it instantiated with JSON-supplied params. Register a new strategy here in
the same commit you add it.
"""

from __future__ import annotations

from src.strategy.breakout import BreakoutParams, DonchianBreakout
from src.strategy.va_breakout import VaBreakout, VaBreakoutParams

STRATEGIES: dict[str, tuple[type, type]] = {
    "breakout": (DonchianBreakout, BreakoutParams),
    "va_breakout": (VaBreakout, VaBreakoutParams),
}


def build(name: str, params: dict):
    """Instantiate the named strategy with ``params`` (a dict from the run config)."""
    try:
        cls, params_cls = STRATEGIES[name]
    except KeyError:
        raise KeyError(f"Unknown strategy {name!r}; known: {list(STRATEGIES)}") from None
    return cls(params_cls(**params))
