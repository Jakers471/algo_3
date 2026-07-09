"""CLI door: record the live market feed to a file.

Thin door - authenticates, resolves the contract, wires MarketHub to Recorder,
and waits. No feed logic here.

Run: ``python -m src.cli.capture --seconds 60``
     ``python -m src.cli.capture --symbol NQ --seconds 300 --depth``
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from src.broker import contracts, market_hub
from src.broker.client import ProjectXClient
from src.capture.recorder import Recorder
from src.config import broker as broker_cfg
from src.config import live as live_cfg
from src.core import console
from src.logging import setup

logger = logging.getLogger(__name__)


def resolve_contract(client: ProjectXClient, symbol: str) -> str:
    """Find the tradable contract id for a symbol, e.g. NQ -> CON.F.US.ENQ.U26."""
    found = contracts.search_contracts(client, symbol, live=False)
    if not found:
        raise SystemExit(f"No contract found for {symbol!r}")
    # The API returns the front month first for a bare root symbol.
    contract = found[0]
    logger.info("Resolved %s -> %s (%s)", symbol, contract.get("id"), contract.get("description"))
    return contract["id"]


def capture(contract_id: str, seconds: int, streams: list[tuple]) -> Recorder:
    """Record `seconds` of live events for one contract, then stop cleanly."""
    client = ProjectXClient(broker_cfg.API_BASE, broker_cfg.USERNAME,
                            broker_cfg.API_KEY, broker_cfg.TOKEN)
    client.connect()

    hub = market_hub.MarketHub(broker_cfg.MARKET_HUB, client.token, contract_id, streams)
    done = threading.Event()

    with Recorder(contract_id) as rec:
        hub.on_event(rec.handle)
        hub.start()
        print(console.paint(f"  recording {seconds}s -> {rec.path.name}", console.CYAN))
        print(console.paint("  ctrl-c to stop early", console.DIM))

        try:
            done.wait(timeout=seconds)
        except KeyboardInterrupt:
            print(console.paint("\n  stopping early", console.YELLOW))
        finally:
            hub.stop()
            time.sleep(0.3)  # let in-flight events land before the file closes

    return rec


def main() -> None:
    setup.setup_logging()
    console.enable_windows_ansi()

    ap = argparse.ArgumentParser(description="Record the live market feed.")
    ap.add_argument("--symbol", default="NQ", help="root symbol to resolve (default NQ)")
    ap.add_argument("--contract", default=None,
                    help=f"explicit contract id (skips lookup; default {live_cfg.DEFAULT_CONTRACT_ID})")
    ap.add_argument("--seconds", type=int, default=60, help="how long to record")
    ap.add_argument("--depth", action="store_true", help="also record the DOM (high volume)")
    args = ap.parse_args()

    streams = [market_hub.TRADES, market_hub.QUOTES]
    if args.depth:
        streams.append(market_hub.DEPTH)

    if args.contract:
        contract_id = args.contract
    else:
        client = ProjectXClient(broker_cfg.API_BASE, broker_cfg.USERNAME,
                                broker_cfg.API_KEY, broker_cfg.TOKEN)
        client.connect()
        contract_id = resolve_contract(client, args.symbol)

    rec = capture(contract_id, args.seconds, streams)

    print()
    total = sum(rec.counts.values())
    color = console.GREEN if total else console.RED
    print(console.paint(f"  {total} events", console.BOLD, color) + f"  -> {rec.path}")
    for event, n in sorted(rec.counts.items()):
        print(f"    {event:<16}{n:>8,}")
    if not total:
        print(console.paint("  Nothing arrived. Market closed, or wrong contract id.", console.YELLOW))
    print()


if __name__ == "__main__":
    main()
