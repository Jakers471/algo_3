"""CLI door: pick a random explore session to replay.

Thin door - picks, prints, and can open the chart on it. No selection logic
here; see src/session_history/pick.py.

``--open`` is the point. The chart's date box is a `datetime-local` input, which
cannot be pasted into from a terminal in any pleasant way, and this tool already
knows the exact moment - so it navigates there itself
(``/?symbol=..&tf=..&at=<epoch>``) rather than printing a string to retype. The
timestamps are still printed for the manual path and for the record.

    python -m src.cli.explore_session --open            # pick one, open the chart there
    python -m src.cli.explore_session                   # just list some
    python -m src.cli.explore_session --name NY         # NY only
    python -m src.cli.explore_session --seed 7          # repeatable
    python -m src.cli.explore_session --count 5         # a few to work through
"""

from __future__ import annotations

import argparse
import random
import webbrowser
from datetime import datetime, timezone

from src.chart import link
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
    ap.add_argument("--open", action="store_true",
                    help="open the chart on the first pick (needs the server up; "
                         "python -m src.cli.chart --study does both)")
    ap.add_argument("--url", default=None, help="chart base URL")
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

    base = args.url or link.base_url()
    name, start = chosen[0]
    url = link.deep_link(base, args.symbol, args.timeframe, start)

    if args.open:
        # Never open a tab at a server that is not there. ERR_CONNECTION_REFUSED
        # blames the network for what is really "nothing is listening", and the
        # page cannot say the one thing the reader needs to know.
        if not link.is_serving():
            print(console.paint("  the chart server is not running, so there is "
                                "nothing to open.", console.YELLOW))
            print(console.paint("  start it and study in one step:", console.DIM))
            print(console.paint(f"      python -m src.cli.chart --study"
                                f"{' ' + args.name if args.name else ''}",
                                console.CYAN))
            print(console.paint("  or serve first (python -m src.cli.chart), then "
                                "re-run this.", console.DIM))
            print()
            raise SystemExit(1)
        print(console.paint(f"  opening the chart on {name} "
                            f"{_utc(start):%Y-%m-%d %H:%M} UTC", console.CYAN))
        print(console.paint(f"  {url}", console.DIM))
        webbrowser.open(url)
    else:
        print(console.paint("  serve and study in one step:  "
                            "python -m src.cli.chart --study", console.DIM))
        print(console.paint(f"  or, with the chart already up:  {url}", console.DIM))
    print()


if __name__ == "__main__":
    main()
