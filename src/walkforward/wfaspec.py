"""The walk-forward run config: the JSON recipe for a WFA run.

One job: hold what a walk-forward run needs - the strategy, the param grid to
search, the objective to optimize, and the IS/OOS window sizes. Like RunSpec,
the saved wfa.json manifest is a superset, so any past WFA run replays.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from src.backtest.runspec import check_config_name


@dataclass
class WFASpec:
    strategy: str
    param_grid: dict = field(default_factory=dict)
    symbol: str = "NQ"
    timeframe: str = "5m"
    size: int = 1
    objective: str = "profit_factor"
    is_days: int = 730
    oos_days: int = 180
    step_days: int = 180
    anchored: bool = False
    min_trades: int = 10  # reject IS combos with fewer trades (selection-bias guard)

    @classmethod
    def from_dict(cls, d: dict) -> "WFASpec":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def load(cls, path: str | Path) -> "WFASpec":
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            spec = cls.from_dict(json.load(fh))
        check_config_name(path, spec.strategy, spec.symbol, spec.timeframe)
        return spec

    def to_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        return f"wfa_{self.strategy}_{self.symbol}{self.timeframe}_{self.objective}"
