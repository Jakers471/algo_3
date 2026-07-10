"""The snapshot: everything true at one instant, as one flat row.

One job: define what a replay step emits. A snapshot is the bar that just
closed, every indicator field computed from it, and any drawings that field
change produced - stamped with market time, immutable, and built only from
events at or before that time.

The history of snapshots is a table. That table is the TUI view, and it is what
the brain will read. Same object, several consumers: the chart draws a row, the
TUI prints a row, the brain scores a row. Nothing recomputes anything, so they
cannot disagree.

``fields`` is deliberately flat and named. Columns, not nesting - because a
column is what a table renders and what a scoring rule reads. An indicator that
could not honestly compute contributes ``None``, never a proxy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Snapshot:
    """One row: the bar, the fields it produced, and what to draw."""

    #: Monotonic per session. Lets a subscriber detect a dropped message.
    seq: int

    #: Dataset index of the bar that just closed, and the dataset size.
    index: int
    total: int

    #: Market time (epoch seconds, UTC) of that bar's close.
    time: int

    #: The bar itself, for renderers that draw candles.
    bar: dict[str, float]

    #: Indicator output. Flat, named, ``None`` where a value is unavailable.
    fields: dict[str, Any] = field(default_factory=dict)

    #: Drawing instructions produced by THIS bar (e.g. a session opened).
    marks: list[dict] = field(default_factory=list)

    #: True once the cursor has consumed the dataset.
    at_end: bool = False

    #: Which timeframe produced this row. The session's own on a base bar; a
    #: coarser one on a rung of the ladder. A subscriber that wants one scale
    #: filters on it, and a subscriber that wants all three does not.
    rung: str = ""

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "index": self.index,
            "total": self.total,
            "time": self.time,
            "bar": self.bar,
            "fields": self.fields,
            "marks": self.marks,
            "at_end": self.at_end,
            "rung": self.rung,
        }
