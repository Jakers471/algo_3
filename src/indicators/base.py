"""What an indicator is: a state machine over the event stream.

One job: define the interface every indicator implements, and the exception it
raises when asked for something it cannot honestly compute.

An indicator consumes events one at a time, in order, and after each one exposes
its current fields. It never sees the whole series, never indexes forward, and
never receives an event twice. This is why the same indicator code runs over
bars, over ticks, and over the live feed - and why it cannot look ahead.

    class MyIndicator(Indicator):
        id = "my_indicator"
        fields = ("value", "state")     # names it publishes into the snapshot row
        depends = ()                    # ids of indicators whose fields it reads

        def reset(self): ...
        def update(self, event, upstream) -> dict: ...

``update`` returns a dict keyed by this indicator's ``fields``. ``upstream`` holds
the fields already produced for this event by the indicators in ``depends`` - so
a regime indicator reads ``delta`` and ``range`` without recomputing them. The
registry topologically sorts by ``depends``; a cycle is a startup error.

**Honesty rule.** An indicator that needs information a source does not carry
must raise ``Unavailable``, never return a proxy. Volume delta, absorption,
sweeps and spread are not recoverable from bars - that information was never
written down. A proxy delta is worse than no delta, because the backtest will
trust it. See BUILD_PLAN.md.
"""

from __future__ import annotations

import importlib
import importlib.util
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Unavailable(RuntimeError):
    """This indicator cannot be computed from this kind of event. Not a bug."""


class Indicator(ABC):
    """A state machine over events, publishing named fields."""

    #: Unique. Used for dependency wiring and as the config module name.
    id: str = ""

    #: The field names this indicator publishes into the snapshot row.
    fields: tuple[str, ...] = ()

    #: Ids of indicators this one reads. Empty means it reads only raw events.
    depends: tuple[str, ...] = ()

    #: field name -> (unit, what it is). One entry per published field.
    #:
    #: The UNIT is the thing a reader gets wrong first. "price" and "points" and
    #: "x range_scale" look identical in a table and mean completely different
    #: things: a price moves with the market, points move with volatility, and a
    #: multiple of range_scale moves with neither. Say which.
    #:
    #: Written here, beside the code that computes the number, so `FIELDS.md` and
    #: the table's help are generated rather than maintained. A field with no
    #: entry fails tests/test_fields.py.
    about: dict[str, tuple[str, str]] = {}

    @abstractmethod
    def reset(self) -> None:
        """Drop all state. Called before a replay seed or a fresh run."""

    @abstractmethod
    def update(self, event: Any, upstream: dict[str, Any] | None = None) -> dict[str, Any]:
        """Consume one event; return this indicator's current fields.

        ``upstream`` maps field name -> value for everything already computed for
        THIS event by the indicators in ``depends``. Raise ``Unavailable`` if the
        event type carries nothing this indicator can use.
        """

    @classmethod
    def provenance(cls) -> dict:
        """Where this indicator's numbers come from, and what tunes them.

        A snapshot row is a flat wall of names. Six months from now nobody -
        human or model - can tell which file computed ``retrace``, which dial
        moved it, or what it was allowed to read. This is that answer, derived
        from the code rather than written beside it, so it cannot drift.
        """
        module = importlib.import_module(cls.__module__)
        config = f"src.config.indicators.{cls.id}"
        has_config = importlib.util.find_spec(config) is not None

        return {
            "id": cls.id,
            "fields": list(cls.fields),
            "depends": list(cls.depends),
            "source": _repo_path(module.__file__),
            "config": _repo_path(importlib.import_module(config).__file__)
            if has_config else None,
            "doc": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
            "about": {name: {"unit": unit, "means": means}
                      for name, (unit, means) in cls.about.items()},
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.id!r} fields={self.fields}>"


def _repo_path(path: str) -> str:
    """An absolute module path as the repo-relative one a reader can open."""
    resolved = Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()
