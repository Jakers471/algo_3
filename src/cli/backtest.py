"""CLI door: run a backtest from a JSON run config and save a labeled run.

Thin door - loads a run config, loads the bars it needs, runs the strategy
through the engine with a progress bar, prints the All/Long/Short summary, and
saves everything (trades, summary, equity image, manifest) to a labeled run
folder. No trading logic here. A run is always defined by a config.

    python -m src.cli.backtest run_configs/breakout_nq5m.json
"""

from __future__ import annotations

import argparse

from src.backtest import engine, runspec
from src.config import backtest as bt_cfg
from src.core import console
from src.core.progress import ProgressBar
from src.data import prepare
from src.logging import setup
from src.reporting import console as report_console
from src.reporting import run, stats
from src.strategy import registry


def main() -> None:
    setup.setup_logging()
    ap = argparse.ArgumentParser(description="Run a backtest from a JSON run config and save a labeled run.")
    ap.add_argument("config", help="path to a JSON run config (see run_configs/)")
    ap.add_argument("--no-save", action="store_true", help="print only; do not save a run folder")
    args = ap.parse_args()

    spec = runspec.RunSpec.load(args.config)
    strategy = registry.build(spec.strategy, spec.params)
    bars = prepare.get_bars(spec.symbol, spec.timeframe)

    bar = ProgressBar(len(bars), "backtest")
    trades = engine.run(bars, strategy, spec.symbol, size=spec.size, progress=bar)
    bar.close()

    summary = stats.compute_all(trades, bt_cfg.STARTING_CAPITAL)
    report_console.report(summary, title=spec.label())

    if not args.no_save:
        meta = {
            "data_start": str(bars.index[0]),
            "data_end": str(bars.index[-1]),
            "n_bars": len(bars),
        }
        run_dir = run.save(spec, trades, summary, bt_cfg.STARTING_CAPITAL, data_meta=meta)
        print(console.paint(f"  saved run -> {run_dir}", console.GREEN))


if __name__ == "__main__":
    main()
