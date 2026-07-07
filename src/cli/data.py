"""CLI door: load prepared bars for a symbol/timeframe and print a summary.

Thin door - parses args, calls ``src.data.prepare.get_bars``, formats a
summary so you can see real bars flowing through the config. No data logic
here. Run: ``python -m src.cli.data NQ 5m``.
"""

from __future__ import annotations

import argparse

from src.core import console
from src.data import loader, prepare
from src.logging import setup


def summarize(symbol: str, timeframe: str) -> None:
    """Load prepared bars and print a compact, color-coded summary."""
    df = prepare.get_bars(symbol, timeframe)
    gaps = int(df["gap_before"].sum())
    zero = int((df["volume"] == 0).sum())

    print()
    print(console.paint(f"  {symbol} {timeframe}  prepared bars", console.BOLD, console.CYAN))
    print(f"  {'rows':<10}{len(df):,}")
    print(f"  {'range':<10}{df.index[0]}  ->  {df.index[-1]}")
    print(f"  {'gaps':<10}{gaps:,}   " + console.paint("(session boundaries)", console.DIM))
    print(f"  {'zero-vol':<10}{zero:,}")
    print(f"  {'columns':<10}{list(df.columns)}")
    print()


def main() -> None:
    setup.setup_logging()
    ap = argparse.ArgumentParser(description="Load and summarize prepared bars.")
    ap.add_argument("symbol", nargs="?", default="NQ", choices=loader.SYMBOLS)
    ap.add_argument("timeframe", nargs="?", default="5m", choices=list(loader.TIMEFRAMES))
    args = ap.parse_args()
    summarize(args.symbol, args.timeframe)


if __name__ == "__main__":
    main()
