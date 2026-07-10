"""Hold the indicators, order them, and run one event through all of them.

One job: own the set of live indicators, sort them so an indicator always runs
after the ones it depends on, and produce the merged field dict for each event.

Dependency order is resolved once, at construction, by topological sort. A cycle
is a startup error - not a silently wrong number three hours into a backtest.

This is the seam the snapshot row is built on (BUILD_PLAN.md phase 3): the merged
dict this returns per event IS the row. Nothing here knows about charts or TUIs.
"""

from __future__ import annotations

import logging
from typing import Any

from src.indicators.base import Indicator, Unavailable

logger = logging.getLogger(__name__)


class CircularDependency(RuntimeError):
    """Indicators depend on each other in a loop; there is no valid run order."""


class Registry:
    """An ordered set of indicators, run together over one event stream."""

    def __init__(self, indicators: list[Indicator]) -> None:
        self._by_id = {ind.id: ind for ind in indicators}
        if len(self._by_id) != len(indicators):
            raise ValueError("duplicate indicator id")
        self._order = _toposort(self._by_id)
        logger.debug("Indicator run order: %s", [i.id for i in self._order])

    @property
    def order(self) -> list[Indicator]:
        return list(self._order)

    def has(self, indicator_id: str) -> bool:
        """Is this indicator running? Lets a caller skip work nothing will read."""
        return indicator_id in self._by_id

    def get(self, indicator_id: str):
        """The live indicator, or None. For a caller that must tune it, not read it."""
        return self._by_id.get(indicator_id)

    def field_names(self) -> list[str]:
        """Every field the row will carry, in run order. The TUI's columns."""
        return [name for ind in self._order for name in ind.fields]

    def provenance(self) -> list[dict]:
        """Every running indicator: its fields, its source file, its config file.

        The contract between a column and the code that filled it. Derived from
        the classes themselves, in dependency order, so it cannot fall out of
        step with what actually ran.
        """
        return [ind.provenance() for ind in self._order]

    def field_source(self) -> dict[str, str]:
        """field name -> the id of the indicator that publishes it."""
        return {name: ind.id for ind in self._order for name in ind.fields}

    def field_groups(self) -> list[dict]:
        """The same fields, still in run order, but labelled by who published them.

        A flat list of names loses the one thing a reader needs: `swing_price`
        and `bos_level` are both prices of swing points, and only the indicator
        that emitted them says which question each answers. A view that groups by
        producer can show that; a flat list cannot.
        """
        return [{
            "id": ind.id,
            "fields": list(ind.fields),
            # Carried to every subscriber, so the table can say what a column
            # means without importing the indicator that made it.
            "about": {name: {"unit": unit, "means": means}
                      for name, (unit, means) in ind.about.items()},
        } for ind in self._order]

    def reset(self) -> None:
        for ind in self._order:
            ind.reset()

    def update(self, event) -> dict[str, Any]:
        """Feed one event to every indicator; return the merged field dict.

        An indicator that raises ``Unavailable`` contributes None for its fields
        rather than a proxy value - the row records that the number is *absent*,
        which is a fact, not a failure.
        """
        row: dict[str, Any] = {}
        for ind in self._order:
            upstream = {k: row[k] for dep in ind.depends for k in self._by_id[dep].fields if k in row}
            try:
                row.update(ind.update(event, upstream))
            except Unavailable:
                row.update({name: None for name in ind.fields})
        return row


def _toposort(by_id: dict[str, Indicator]) -> list[Indicator]:
    """Depth-first topological sort. Raises on a cycle or an unknown dependency."""
    order: list[Indicator] = []
    state: dict[str, int] = {}  # 0 = unvisited, 1 = visiting, 2 = done

    def visit(ind_id: str, path: tuple[str, ...]) -> None:
        if state.get(ind_id) == 2:
            return
        if state.get(ind_id) == 1:
            raise CircularDependency(" -> ".join([*path, ind_id]))
        state[ind_id] = 1
        ind = by_id.get(ind_id)
        if ind is None:
            raise KeyError(f"indicator {ind_id!r} depends on an unregistered indicator")
        for dep in ind.depends:
            if dep not in by_id:
                raise KeyError(f"{ind_id!r} depends on {dep!r}, which is not registered")
            visit(dep, (*path, ind_id))
        state[ind_id] = 2
        order.append(ind)

    for ind_id in by_id:
        visit(ind_id, ())
    return order
