"""CLI door: pick a random explore session to replay.

Thin door - picks, prints, and says where to paste it. No selection logic here;
see src/session_history/pick.py.

The chart's own date box takes UTC, so that is what this prints - the exact
string to paste, not a date the reader has to convert. It also prints the seal's
own verdict, because the one thing this tool exists to guarantee is that what
you are about to stare at is not the vault.

    python -m src.cli.explore_session                    # any tracked session
    python -m src.cli.explore_session --name NY          # NY only
    python -m src.cli.explore_session --seed 7           # repeatable
    python -m src.cli.explore_session --count 5          # a few to work through
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timezone

from src.config import ticks as ticks_cfg
from src.config.indicators import session_stats as ss_cfg
from src.core import console
from src.logging import setup
from src.session_history import pick, split


def _utc(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(
        description="Pick a random explore-side session to replay.")
    ap.add_argument("--symbol", default=ticks_cfg.OUTPUT_SYMBOL)
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--name", default=None, choices=list(ss_cfg.TRACKED_SESSIONS),
                    help="only this session (default: any tracked one)")
    ap.add_argument("--seed", type=int, default=None,
                    help="repeatable pick - same seed, same session")
    ap.add_argument("--count", type=int, default=1,
                    help="how many to pick (default: 1)")
    args = ap.parse_args()

    try:
        sessions = pick.explore_sessions(args.symbol, args.timeframe, args.name)
    except split.NotSealed as exc:
        print(console.paint(f"  {exc}", console.YELLOW))
        raise SystemExit(1)

    if not sessions:
        print(console.paint(f"  no explore sessions for {args.symbol} "
                            f"{args.timeframe}", console.YELLOW))
        raise SystemExit(1)

    chosen = random.Random(args.seed).sample(
        sessions, min(args.count, len(sessions)))

    print()
    print(console.paint(f"  {len(sessions):,} explore sessions available "
                        f"({args.symbol} {args.timeframe})", console.DIM))
    print(console.paint(f"  sealed from {_utc(split.cutoff()):%Y-%m-%d} - "
                        f"nothing below is from the vault", console.DIM))
    print()
    for name, start in chosen:
        stamp = _utc(start)
        print(f"  {console.paint(name.ljust(7), console.CYAN)}"
              f"  {console.paint(stamp.strftime('%Y-%m-%dT%H:%M'), console.GREEN)}"
              f"  {console.paint(stamp.strftime('(%a %d %b %Y, %H:%M UTC)'), console.DIM)}")
    print()
    print(console.paint("  paste the green value into the chart's date box "
                        "(it reads UTC), then Go.", console.DIM))
    print()


if __name__ == "__main__":
    main()
