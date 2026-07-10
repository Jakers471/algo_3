"""CLI door: open the desktop snapshot table.

Thin door - resolves which replay session to watch, opens the stream, shows the
window. No table logic here.

Run the chart first (``python -m src.cli.chart --open``), hit Replay, click a
bar; then:

    python -m src.cli.table                       # attach to the running replay
    python -m src.cli.table --symbol NQT --timeframe 5m   # start one of its own
    python -m src.cli.table --rung 15m            # the 15m scale of that replay

One replay publishes a row per rung of its ladder - the same market, folded into
a coarser bar, with its own indicator state. Three tables on three rungs are
three filters over ONE cursor, so they cannot drift apart. Open three.
"""

from __future__ import annotations

import argparse
import sys

from src.config import table as cfg
from src.core import console
from src.logging import setup
from src.table import client


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Desktop table of replay snapshots.")
    ap.add_argument("--url", default=cfg.SERVER_URL, help="chart server base URL")
    ap.add_argument("--session", default=None, help="attach to this session id")
    ap.add_argument("--symbol", default=None, help="start a new replay on this symbol")
    ap.add_argument("--timeframe", default=None, help="timeframe for a new replay")
    ap.add_argument("--at", type=int, default=None, help="bar index to cut back to")
    ap.add_argument("--rung", default=None,
                    help="which scale of the replay to show (default: its base)")
    ap.add_argument("--list", action="store_true", help="list running replays and exit")
    args = ap.parse_args()

    if args.list:
        for session in client.list_sessions(args.url):
            rungs = ", ".join(session.get("rungs") or [session["timeframe"]])
            print(f"  {session['id']}  {session['symbol']:<5} {session['timeframe']:<4} "
                  f"cursor {session['cursor']:,}  {session['subscribers']} subscriber(s)  "
                  f"rungs: {rungs}")
        return

    try:
        session = client.resolve_session(args.url, args.session, args.symbol,
                                         args.timeframe, args.at)
    except client.NoSession as exc:
        print(console.paint(f"  {exc}", console.YELLOW))
        sys.exit(1)
    except OSError as exc:
        print(console.paint(f"  cannot reach the chart server at {args.url}: {exc}", console.RED))
        print(console.paint("  start it with: python -m src.cli.chart", console.DIM))
        sys.exit(1)

    # Imported late: Qt takes a moment to load, and a bad --session should fail
    # before a window ever appears.
    from PySide6.QtWidgets import QApplication

    from src.table.window import TableWindow

    rungs = session.get("rungs") or [session["timeframe"]]
    rung = args.rung or session["timeframe"]
    if rung not in rungs:
        # A rung is folded UP from the replay's own bars, so a 15m replay can
        # never produce a 30s row - the bars to fold do not exist. Say which
        # replay would, rather than opening a window that stays empty.
        print()
        print(console.paint(f"  this replay ({session['symbol']} "
                            f"{session['timeframe']}) has no {rung} rung.", console.YELLOW))
        print(console.paint(f"  it publishes: {', '.join(rungs)}", console.DIM))
        print(console.paint(f"  for a {rung} table, replay a timeframe {rung} folds up from "
                            f"- e.g. hit Replay on the chart at 30s.", console.DIM))
        print()
        sys.exit(1)

    stream = client.SnapshotStream(args.url, session["id"], rung=rung)
    stream.start()

    print()
    print(console.paint(f"  watching session {session['id']}  "
                        f"({session['symbol']} {rung})", console.CYAN))
    if len(rungs) > 1:
        print(console.paint(f"  this replay also publishes: "
                            f"{', '.join(r for r in rungs if r != rung)}", console.DIM))
    print(console.paint("  drive it from the chart; close the window to detach", console.DIM))
    print()

    app = QApplication(sys.argv)
    window = TableWindow(stream, {**session, "timeframe": rung})
    window.show()
    code = app.exec()
    stream.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
