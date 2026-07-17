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
from urllib.parse import urlencode

from src.config import chart as chart_cfg
from src.config import ticks as ticks_cfg
from src.config.indicators import session_stats as ss_cfg
from src.core import console
from src.logging import setup
from src.session_history import pick, split


def _utc(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def _base_url() -> str:
    return f"http://{chart_cfg.HOST}:{chart_cfg.PORT}"


def chart_url(base: str, symbol: str, timeframe: str, start: int) -> str:
    """The chart's deep link: it boots straight into replay at this bar."""
    query = urlencode({"symbol": symbol, "tf": timeframe, "at": start})
    return f"{base.rstrip('/')}/?{query}"


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
                    help="open the chart on the first pick (needs the server up)")
    ap.add_argument("--url", default=None,
                    help=f"chart base URL (default: {_base_url()})")
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

    base = args.url or _base_url()
    if args.open:
        name, start = chosen[0]
        url = chart_url(base, args.symbol, args.timeframe, start)
        print(console.paint(f"  opening the chart on {name} "
                            f"{_utc(start):%Y-%m-%d %H:%M} UTC", console.CYAN))
        print(console.paint(f"  {url}", console.DIM))
        # If the server is not up this opens a dead tab, which says so plainly -
        # a nicer failure than this tool silently deciding not to.
        webbrowser.open(url)
        print(console.paint(f"  (not the chart? start it: python -m src.cli.chart)",
                            console.DIM))
    else:
        name, start = chosen[0]
        print(console.paint("  open one straight away:  "
                            "python -m src.cli.explore_session --open", console.DIM))
        print(console.paint(f"  or paste a link:  "
                            f"{chart_url(base, args.symbol, args.timeframe, start)}",
                            console.DIM))
    print()


if __name__ == "__main__":
    main()
