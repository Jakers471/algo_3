"""CLI door: build the volume-at-price store from the tick file.

Thin door - parses arguments, calls the builder, prints what landed. No folding
logic here.

Run: ``python -m src.cli.vap``
     ``python -m src.cli.vap --verify``   also checks it against the bars
"""

from __future__ import annotations

import argparse
import logging
import time

from src.config import ticks as ticks_cfg
from src.core import console, progress
from src.logging import setup
from src.profile import build

logger = logging.getLogger(__name__)


def verify(symbol: str, timeframe: str, samples: int = 500) -> tuple[int, int]:
    """Every bar's histogram must sum to that bar's own volume. Exactly.

    This is the one invariant worth having: if a single contract is lost or
    double-counted, every profile drawn from the store is quietly wrong, and no
    picture would ever show it.
    """
    import numpy as np
    import pandas as pd

    from src.profile import store

    bars = pd.read_parquet(f"data/{symbol}/{symbol}_{timeframe}.parquet",
                           columns=["volume", "buy_volume"])
    step = max(1, len(bars) // samples)
    checked = mismatched = 0

    for ts, row in bars.iloc[::step].iterrows():
        epoch = int(ts.timestamp())
        _, volume, buy = store.histogram(symbol, timeframe, epoch - 1, epoch)
        checked += 1
        if int(volume.sum()) != int(row["volume"]) or int(buy.sum()) != int(row["buy_volume"]):
            mismatched += 1
            if mismatched <= 3:
                logger.error("bar %s: vap volume %d vs bar volume %d",
                             ts, int(volume.sum()), int(row["volume"]))
    return checked, mismatched


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Build volume at price from ticks.")
    ap.add_argument("--symbol", default=ticks_cfg.OUTPUT_SYMBOL)
    ap.add_argument("--timeframe", default=ticks_cfg.BASE_TIMEFRAME,
                    help="the BASE bar the levels are grouped under")
    ap.add_argument("--verify", action="store_true",
                    help="check each sampled bar's histogram sums to its volume")
    ap.add_argument("--skip-build", action="store_true", help="verify only")
    args = ap.parse_args()

    if not args.skip_build:
        import pyarrow.parquet as pq
        started = time.time()
        total = pq.ParquetFile(ticks_cfg.TICK_FILE).metadata.num_rows
        bar = progress.ProgressBar(total, "ticks")
        result = build.build(args.symbol, args.timeframe,
                             progress=lambda seen, _total: bar.update(seen))
        bar.close()
        print(console.paint(f"  {result['levels']:,} price levels", console.BOLD, console.GREEN)
              + f" across {result['bars']:,} {args.timeframe} bars"
              + console.paint(f"   {time.time() - started:.0f}s", console.DIM))
        print(f"    {result['vap']}")
        print(f"    {result['index']}")

    if args.verify:
        print()
        checked, bad = verify(args.symbol, args.timeframe)
        colour = console.GREEN if bad == 0 else console.RED
        print(console.paint(
            f"  {checked - bad}/{checked} sampled bars: the histogram sums to the bar's volume",
            colour))
        if bad:
            raise SystemExit(1)
    print()


if __name__ == "__main__":
    main()
