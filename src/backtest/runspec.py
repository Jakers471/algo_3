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

# Saved run manifests are not curated recipes, so they are exempt from the
# filename rule (they replay by content, whatever the folder is named).
_MANIFESTS = {"run.json", "wfa.json"}


def check_config_name(path: Path, strategy: str, symbol: str, timeframe: str) -> None:
    """Refuse a run config whose filename doesn't reflect the strategy inside.

    Each config is a saved recipe named for its contents; repurposing one file for
    a different strategy makes the name lie. The rule: the strategy name must appear
    in the filename. Manifests (replayed run outputs) are exempt.
    """
    if path.name in _MANIFESTS:
        return
    if strategy.lower() not in path.stem.lower():
        raise ValueError(
            f"Config '{path.name}' sets strategy '{strategy}', but the filename does "
            f"not reflect it. A config is a saved recipe named for its contents - don't "
            f"repurpose a file for a different strategy. Save a new file, e.g. "
            f"'{strategy}_{symbol.lower()}{timeframe}.json', or fix the 'strategy' field."
        )


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
        path = Path(path)
        with open(path, encoding="utf-8") as fh:
            spec = cls.from_dict(json.load(fh))
        check_config_name(path, spec.strategy, spec.symbol, spec.timeframe)
        return spec

    def to_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        """Short slug for the run folder name, e.g. breakout_NQ5m_lookback20_stop20."""
        parts = "_".join(f"{k}{v}" for k, v in self.params.items())
        base = f"{self.strategy}_{self.symbol}{self.timeframe}"
        return f"{base}_{parts}" if parts else base
