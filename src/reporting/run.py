"""Bundle a backtest's outputs into one labeled, replayable run folder.

One job: create runs/<timestamp>_<strategy_symbol_params>/ and write every
artifact - trades (csv/txt), summary (json/txt), equity.png - plus a run.json
manifest. The manifest is a superset of the run config, so it loads straight
back as a RunSpec: every run is reproducible and comparable.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

from src.backtest.runspec import RunSpec
from src.reporting import equity
from src.reporting import stats as stats_mod
from src.reporting import trades as trades_mod

RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"


def _num(v: float):
    """JSON-safe number: inf/nan -> None."""
    return None if (isinstance(v, float) and not math.isfinite(v)) else v


def save(spec: RunSpec, trade_list, stats: dict, starting_capital: float, *, data_meta: dict) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = RUNS_DIR / f"{ts}_{spec.label()}"
    run_dir.mkdir(parents=True, exist_ok=True)

    trades_mod.write_csv(trade_list, run_dir / "trades.csv")
    trades_mod.write_text(trade_list, run_dir / "trades.txt")
    stats_mod.write_json(stats, run_dir / "summary.json")
    stats_mod.write_text(stats, run_dir / "summary.txt")
    equity.plot(trade_list, run_dir / "equity.png", title=spec.label())

    a = stats["all"]
    manifest = {
        **spec.to_dict(),
        "run": {
            "timestamp": ts,
            "starting_capital": starting_capital,
            "n_trades": len(trade_list),
            **data_meta,
        },
        "headline": {
            "net_profit": _num(a.net_profit),
            "win_rate": _num(a.win_rate),
            "profit_factor": _num(a.profit_factor),
            "max_drawdown": _num(a.max_drawdown),
            "ambiguous_pct": _num(a.ambiguous_pct),
        },
    }
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return run_dir
