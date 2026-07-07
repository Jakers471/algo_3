"""Expand a parameter grid into every combination.

One job: turn ``{"lookback": [10, 20], "stop_points": [15, 20]}`` into the list
of concrete param dicts to backtest. Pure, no side effects.
"""

from __future__ import annotations

from itertools import product


def expand(grid: dict[str, list]) -> list[dict]:
    """Every combination of the grid's values, as a list of param dicts."""
    if not grid:
        return [{}]
    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in product(*(grid[k] for k in keys))]
