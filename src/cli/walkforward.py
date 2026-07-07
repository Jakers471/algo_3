"""CLI door: run a walk-forward analysis from a JSON config and save the run.

Thin door - loads a WFA config, loads the bars, runs the walk-forward
(optimize IS -> test OOS -> stitch) with a per-fold progress bar, prints the
fold table + stitched-OOS summary + walk-forward efficiency, and saves a
labeled run. No logic here. A run is always defined by a config.

    python -m src.cli.walkforward run_configs/wfa_breakout_nq5m.json
"""

from __future__ import annotations

import argparse
import logging

from src.config import backtest as bt_cfg
from src.core import console
from src.core.progress import ProgressBar
from src.data import prepare
from src.logging import setup
from src.reporting import console as report_console
from src.reporting import run, stats
from src.walkforward import engine, folds
from src.walkforward.wfaspec import WFASpec


def main() -> None:
    setup.setup_logging()
    # The sweep runs the engine hundreds of times; silence its per-run INFO line.
    logging.getLogger("src.backtest.engine").setLevel(logging.WARNING)

    ap = argparse.ArgumentParser(description="Run a walk-forward analysis and save a labeled run.")
    ap.add_argument("config", help="path to a JSON walk-forward config (see run_configs/)")
    ap.add_argument("--no-save", action="store_true", help="print only; do not save a run folder")
    args = ap.parse_args()

    spec = WFASpec.load(args.config)
    bars = prepare.get_bars(spec.symbol, spec.timeframe)
    n_folds = len(folds.generate(bars.index, spec.is_days, spec.oos_days, spec.step_days, spec.anchored))

    bar = ProgressBar(n_folds, "walk-forward")
    result = engine.run(bars, spec, progress=bar)
    bar.close()

    report_console.report_folds(result.fold_results, spec.objective, result.wfe)
    summary = stats.compute_all(result.oos_trades, bt_cfg.STARTING_CAPITAL)
    report_console.report(summary, title=f"{spec.label()}  (stitched out-of-sample)")

    if not args.no_save:
        meta = {
            "data_start": str(bars.index[0]),
            "data_end": str(bars.index[-1]),
            "n_bars": len(bars),
        }
        run_dir = run.save_wfa(spec, result, bt_cfg.STARTING_CAPITAL, data_meta=meta)
        print(console.paint(f"  saved run -> {run_dir}", console.GREEN))


if __name__ == "__main__":
    main()
