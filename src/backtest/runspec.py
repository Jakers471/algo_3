"""The run config: the JSON recipe that defines one backtest run.

One job: load/hold what a run needs - which strategy, its params, the
instrument/timeframe, and size. The saved run.json manifest is a superset of
this, so any past run's manifest loads straight back as a RunSpec (unknown
keys like results are ignored) - every labeled run is replayable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class RunSpec:
    strategy: str
    params: dict = field(default_factory=dict)
    symbol: str = "NQ"
    timeframe: str = "5m"
    size: int = 1  # temporary: fixed size until the risk/ engine sizes trades

    @classmethod
    def from_dict(cls, d: dict) -> "RunSpec":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def load(cls, path: str | Path) -> "RunSpec":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def to_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        """Short slug for the run folder name, e.g. breakout_NQ5m_lookback20_stop20."""
        parts = "_".join(f"{k}{v}" for k, v in self.params.items())
        base = f"{self.strategy}_{self.symbol}{self.timeframe}"
        return f"{base}_{parts}" if parts else base
