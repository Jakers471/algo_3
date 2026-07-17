"""CLI door: build the chart's bar cache and serve the chart.

Thin door - parses args, calls ``src.chart.server.serve``, prints where to
point a browser. No chart or data logic here. Starting always reclaims the
port from an older chart server, so they never stack.

``--study`` is the whole session-research loop in one command: serve, pick a
random explore-side session, and open the chart on it once the socket is bound.
It lives here rather than in ``explore_session`` because this door already owns
"serve, then open a URL when ready" - the other door can only open a chart
someone else is already serving, and a tool that must be run second is a tool
that gets run first.

Run: ``python -m src.cli.chart``   (--repack after new data, --stop to close)
     ``python -m src.cli.chart --study NY``    serve and open on a random NY session
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from datetime import datetime, timezone

from src.chart import lifecycle, link, packer, server
from src.config import chart as chart_cfg
from src.config import ticks as ticks_cfg
from src.core import console
from src.logging import setup


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Serve the replay chart.")
    ap.add_argument("--host", default=chart_cfg.HOST)
    ap.add_argument("--port", type=int, default=chart_cfg.PORT)
    ap.add_argument("--repack", action="store_true",
                    help="rebuild the packed bar cache from Parquet before serving")
    ap.add_argument("--stop", action="store_true",
                    help="stop a running chart server on this port and exit")
    ap.add_argument("--open", action="store_true",
                    help="open the chart in a browser once the server is listening")
    ap.add_argument("--reload", action="store_true",
                    help="restart automatically when Python changes (HTML/CSS/JS "
                         "already reload on a plain browser refresh)")
    ap.add_argument("--study", nargs="?", const="", default=None, metavar="SESSION",
                    help="serve, then open on a RANDOM explore-side session "
                         "(never the vault). Optionally name one: --study NY")
    ap.add_argument("--study-symbol", default=ticks_cfg.OUTPUT_SYMBOL,
                    help="symbol to study (default: %(default)s)")
    ap.add_argument("--study-timeframe", default="5m",
                    help="timeframe to study (default: %(default)s)")
    args = ap.parse_args()

    try:
        if args.stop:
            lifecycle.stop_running(args.host, args.port)
            print(console.paint(f"  port {args.port} confirmed closed", console.GREEN))
            return

        if args.repack:
            packer.pack_all(force=True)

        url = f"http://{args.host}:{args.port}"
        open_url = url

        if args.study is not None:
            # Picked BEFORE serving: a bad session name or an unsealed dataset
            # should fail here, in the terminal, rather than three seconds later
            # in a browser tab that can only shrug.
            from src.session_history import pick

            name, start = pick.random_explore(
                args.study_symbol, args.study_timeframe, args.study or None)
            open_url = link.deep_link(url, args.study_symbol,
                                      args.study_timeframe, start)
            stamp = datetime.fromtimestamp(start, tz=timezone.utc)
            print()
            print(console.paint(f"  studying {name}  "
                                f"{stamp:%Y-%m-%d %H:%M} UTC", console.CYAN)
                  + console.paint("   (explore-side; the vault is untouched)",
                                  console.DIM))

        print()
        print(console.paint("  chart", console.BOLD, console.CYAN) + f"   {url}")
        print(console.paint("  ctrl-c to stop", console.DIM))
        print()
        # Only after the socket is bound - the first run packs bars for seconds.
        want_open = args.open or args.study is not None
        on_ready = (lambda _ready: webbrowser.open(open_url)) if want_open else None
        restart = server.serve(args.host, args.port, on_ready=on_ready, reload=args.reload)

        if restart:
            # Re-exec rather than re-serve in place: the point of a reload is to
            # re-import every module, and only a fresh interpreter does that.
            # The port is already confirmed free by the shutdown we just finished.
            print(console.paint("  reloading...", console.DIM))
            os.execv(sys.executable, [sys.executable, "-m", "src.cli.chart",
                                      "--host", args.host, "--port", str(args.port),
                                      "--reload"])
    except lifecycle.PortBusy as exc:
        print(console.paint(f"  {exc}", console.RED))
        sys.exit(1)


if __name__ == "__main__":
    main()
