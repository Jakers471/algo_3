"""CLI door: run a breakout backtest over prepared bars and print results.

Thin door - parses args, loads bars (src.data.prepare), runs the strategy
through the backtest engine, prints metrics. No trading logic here.
Run: ``python -m src.cli.backtest NQ 5m --lookback 20 --stop 20 --target 40``.
"""

from __future__ import annotations

import argparse

from src.backtest import engine, results
from src.config import backtest as bt_cfg
from src.data import loader, prepare
from src.logging import setup
from src.strategy.breakout import BreakoutParams, DonchianBreakout


def main() -> None:
    setup.setup_logging()
    ap = argparse.ArgumentParser(description="Run a breakout backtest.")
    ap.add_argument("symbol", nargs="?", default="NQ", choices=loader.SYMBOLS)
    ap.add_argument("timeframe", nargs="?", default="5m", choices=list(loader.TIMEFRAMES))
    ap.add_argument("--lookback", type=int, default=20, help="breakout lookback in bars")
    ap.add_argument("--stop", type=float, default=20.0, help="stop-loss distance in points")
    ap.add_argument("--target", type=float, default=40.0, help="take-profit distance in points")
    args = ap.parse_args()

    bars = prepare.get_bars(args.symbol, args.timeframe)
    strategy = DonchianBreakout(BreakoutParams(args.lookback, args.stop, args.target))
    trades = engine.run(bars, strategy, args.symbol)
    metrics = results.summarize(trades, bt_cfg.STARTING_CAPITAL)
    results.report(
        metrics,
        title=f"{args.symbol} {args.timeframe}  breakout(lb={args.lookback}, "
              f"stop={args.stop}, tgt={args.target})",
    )


if __name__ == "__main__":
    main()
