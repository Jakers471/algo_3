"""CLI door: rebuild bars from the tick file, including order flow.

Thin door - parses args, calls ``src.data.resample``, writes Parquet under the
tick dataset's own symbol, and prints what landed. No resampling logic here.

Run: ``python -m src.cli.resample``            (all timeframes)
     ``python -m src.cli.resample --only 15s``
"""

from __future__ import annotations

import argparse
import sys
import time

from src.config import ticks as cfg
from src.core import console
from src.data import loader, resample
from src.logging import setup


def _write(bars, timeframe: str) -> str:
    out_dir = loader.DATA_DIR / cfg.OUTPUT_SYMBOL
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{cfg.OUTPUT_SYMBOL}_{timeframe}.parquet"
    bars.to_parquet(path)
    return path


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Rebuild bars from the tick file.")
    ap.add_argument("--only", default=None, help="one timeframe (default: all)")
    args = ap.parse_args()

    if not cfg.TICK_FILE.exists():
        print(console.paint(f"  no tick file at {cfg.TICK_FILE}", console.RED))
        sys.exit(1)

    def progress(seen: int, total: int) -> None:
        pct = 100.0 * seen / total
        print(f"\r  ticks {seen:,} / {total:,}  ({pct:5.1f}%)", end="", flush=True)

    started = time.time()
    base = resample.base_bars(progress=progress)
    print()

    wanted = [args.only] if args.only else [cfg.BASE_TIMEFRAME, *cfg.DERIVED_TIMEFRAMES]
    print()
    print(console.paint(f"  {cfg.OUTPUT_SYMBOL}  bars rebuilt from ticks", console.BOLD, console.CYAN))
    print(f"  {'tf':<6}{'bars':>12}{'first':>22}{'last':>22}")
    for timeframe in wanted:
        bars = base if timeframe == cfg.BASE_TIMEFRAME else resample.derive(base, timeframe)
        path = _write(bars, timeframe)
        print(f"  {timeframe:<6}{len(bars):>12,}{str(bars.index[0]):>22}{str(bars.index[-1]):>22}")

    print()
    print(console.paint(f"  done in {time.time() - started:.0f}s -> data/{cfg.OUTPUT_SYMBOL}/", console.GREEN))
    print(console.paint("  run 'python -m src.cli.chart --repack' to see them on the chart", console.DIM))
    print()


if __name__ == "__main__":
    main()
