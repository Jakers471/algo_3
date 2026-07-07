"""CLI door: run a backtest from a JSON config (or args) and save a labeled run.

Thin door - loads a run config, loads the bars it needs, runs the strategy
through the engine with a progress bar, prints the All/Long/Short summary, and
saves everything (trades, summary, equity image, manifest) to a labeled run
folder. No trading logic here.

    python -m src.cli.backtest --config run_configs/breakout_nq5m.json
    python -m src.cli.backtest NQ 5m --lookback 20 --stop 20 --target 40
"""

from __future__ import annotations

import argparse

from src.backtest import engine, runspec
from src.config import backtest as bt_cfg
from src.core import console
from src.core.progress import ProgressBar
from src.data import loader, prepare
from src.logging import setup
from src.reporting import console as report_console
from src.reporting import run, stats
from src.strategy import registry


def _spec_from_args(args: argparse.Namespace) -> runspec.RunSpec:
    if args.config:
        return runspec.RunSpec.load(args.config)
    return runspec.RunSpec(
        strategy="breakout",
        params={"lookback": args.lookback, "stop_points": args.stop, "target_points": args.target},
        symbol=args.symbol,
        timeframe=args.timeframe,
    )


def main() -> None:
    setup.setup_logging()
    ap = argparse.ArgumentParser(description="Run a backtest and save a labeled run.")
    ap.add_argument("symbol", nargs="?", default="NQ", choices=loader.SYMBOLS)
    ap.add_argument("timeframe", nargs="?", default="5m", choices=list(loader.TIMEFRAMES))
    ap.add_argument("--config", help="path to a JSON run config (overrides positional args)")
    ap.add_argument("--lookback", type=int, default=20, help="breakout lookback in bars")
    ap.add_argument("--stop", type=float, default=20.0, help="stop-loss distance in points")
    ap.add_argument("--target", type=float, default=40.0, help="take-profit distance in points")
    ap.add_argument("--no-save", action="store_true", help="print only; do not save a run folder")
    args = ap.parse_args()

    spec = _spec_from_args(args)
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
