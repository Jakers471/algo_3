"""CLI door: build the session-history percentile table.

Thin door - parses arguments, calls the builder, prints what landed. No
walking or reduction logic here; see src/session_history/build.py.

Run: ``python -m src.cli.session_history --symbol NQT --timeframe 5m``
"""

from __future__ import annotations

import argparse
import time

from src.config.indicators import session_stats as ss_cfg
from src.config import ticks as ticks_cfg
from src.core import console
from src.logging import setup
from src.session_history import build


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(
        description="Build session_stats' percentile-vs-history table.")
    ap.add_argument("--symbol", default=ticks_cfg.OUTPUT_SYMBOL)
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--explore-only", action="store_true",
                    help="drop sealed sessions (SESSION_SPLIT.json). Required before "
                         "any evaluation ON sealed data; the full-history default is "
                         "for the live card only.")
    args = ap.parse_args()

    started = time.time()
    result = build.build(args.symbol, args.timeframe, explore_only=args.explore_only)

    print()
    print(console.paint(f"  wrote {result['path']}", console.BOLD, console.GREEN)
          + console.paint(f"   {time.time() - started:.1f}s", console.DIM))
    for name in ss_cfg.TRACKED_SESSIONS:
        print(f"    {name:<8} {result['sessions'][name]:,} sessions")
    print()


if __name__ == "__main__":
    main()
