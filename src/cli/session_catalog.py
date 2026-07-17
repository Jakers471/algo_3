"""CLI door: build the session catalog (the card, every explore session, every bar).

Thin door - parses arguments, calls the builder, prints what landed. The
walking and the vault enforcement live in src/session_history/catalog.py.

Run: ``python -m src.cli.session_catalog``
     ``python -m src.cli.session_catalog --include-sealed``   ONLY for the one
     honest final evaluation of an already-frozen rule.
"""

from __future__ import annotations

import argparse
import time

from src.config import ticks as ticks_cfg
from src.core import console, progress
from src.logging import setup
from src.session_history import catalog


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Build the per-bar session catalog.")
    ap.add_argument("--symbol", default=ticks_cfg.OUTPUT_SYMBOL)
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--include-sealed", action="store_true",
                    help="ALSO write the sealed catalog, to its own separate file. "
                         "Only for the final evaluation of a frozen rule.")
    args = ap.parse_args()

    if args.include_sealed:
        print(console.paint(
            "\n  --include-sealed: writing the vault's rows too. If a rule is not\n"
            "  already frozen, stop - looking at these spends them permanently.",
            console.YELLOW))

    bar = progress.ProgressBar(1, "catalog")

    def tick(done: int, total: int) -> None:
        bar.total = max(total, 1)
        bar.update(done)

    started = time.time()
    written = catalog.build_catalog(args.symbol, args.timeframe,
                                    include_sealed=args.include_sealed, progress=tick)
    bar.close()

    print()
    for label, info in written.items():
        print(console.paint(f"  {label:<8}", console.BOLD)
              + f" {info['rows']:,} rows, {info['sessions']:,} sessions"
              + f"  -> {info['path']}")
    print(console.paint(f"  {time.time() - started:.1f}s", console.DIM))
    print()


if __name__ == "__main__":
    main()
