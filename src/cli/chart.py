"""CLI door: build the chart's bar cache and serve the chart.

Thin door - parses args, calls ``src.chart.server.serve``, prints where to
point a browser. No chart or data logic here. Starting always reclaims the
port from an older chart server, so they never stack.

Run: ``python -m src.cli.chart``   (--repack after new data, --stop to close)
"""

from __future__ import annotations

import argparse
import sys
import webbrowser

from src.chart import lifecycle, packer, server
from src.config import chart as chart_cfg
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
    args = ap.parse_args()

    try:
        if args.stop:
            lifecycle.stop_running(args.host, args.port)
            print(console.paint(f"  port {args.port} confirmed closed", console.GREEN))
            return

        if args.repack:
            packer.pack_all(force=True)

        url = f"http://{args.host}:{args.port}"
        print()
        print(console.paint("  chart", console.BOLD, console.CYAN) + f"   {url}")
        print(console.paint("  ctrl-c to stop", console.DIM))
        print()
        # Only after the socket is bound - the first run packs bars for seconds.
        on_ready = (lambda ready_url: webbrowser.open(ready_url)) if args.open else None
        server.serve(args.host, args.port, on_ready=on_ready)
    except lifecycle.PortBusy as exc:
        print(console.paint(f"  {exc}", console.RED))
        sys.exit(1)


if __name__ == "__main__":
    main()
