"""CLI command: connect, select an account, and grab NQ futures data.

One job: orchestration. This is a thin door — it parses nothing complex,
calls the real functions in the broker modules, and formats the result with
neat, color-coded output. No trading logic lives here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src import console
from src.broker import accounts, contracts, history
from src.broker.client import ProjectXClient
from src.config import get_settings
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

# The E-mini Nasdaq-100 future (not the Micro, which is F.US.MNQ).
NQ_SYMBOL_ID = "F.US.ENQ"


def _header(text: str) -> None:
    logger.info(console.paint(text, console.BOLD, console.CYAN))


def run() -> None:
    setup_logging(logging.INFO)
    settings = get_settings()

    # 1) Connect ---------------------------------------------------------
    _header("Step 1  Connect to ProjectX")
    client = ProjectXClient(settings)
    client.connect()

    # 2) Select an account ----------------------------------------------
    _header("Step 2  Select an account")
    accts = accounts.search_accounts(client, only_active=True)
    for a in accts:
        flag = console.paint("tradable", console.GREEN) if a.get("canTrade") else console.paint("no-trade", console.YELLOW)
        logger.info(
            "  %-22s id=%-8s balance=%s  %s",
            a.get("name"),
            a.get("id"),
            console.paint(f"${a.get('balance'):,}", console.WHITE),
            flag,
        )
    chosen = accounts.select_tradable(accts)
    if not chosen:
        logger.error("No accounts available.")
        return
    logger.info("Selected: %s", console.paint(f"{chosen.get('name')} (id={chosen.get('id')})", console.BOLD, console.GREEN))

    # 3) Grab NQ futures data -------------------------------------------
    _header("Step 3  Grab NQ futures data")
    found = contracts.search_contracts(client, "NQ")
    contract = contracts.resolve_symbol(found, NQ_SYMBOL_ID)
    if not contract:
        logger.error("Could not resolve the E-mini NQ contract (%s).", NQ_SYMBOL_ID)
        return
    logger.info(
        "Contract: %s  %s",
        console.paint(contract.get("id"), console.BOLD, console.GREEN),
        console.paint(contract.get("description", ""), console.DIM),
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    bars = history.retrieve_bars(
        client,
        contract_id=contract["id"],
        start=start,
        end=end,
        unit=history.UNIT_HOUR,
        unit_number=1,
        limit=200,
    )
    if not bars:
        logger.warning("No bars returned for the requested window.")
        return

    logger.info("Most recent hourly bars (newest first):")
    logger.info(
        console.paint("  %-25s %10s %10s %10s %10s %8s", console.DIM),
        "time", "open", "high", "low", "close", "vol",
    )
    for bar in bars[:5]:
        logger.info(
            "  %-25s %10.2f %10.2f %10.2f %10.2f %8s",
            bar["t"], bar["o"], bar["h"], bar["l"], bar["c"], bar["v"],
        )
    logger.info(console.paint("Done. Connection, account, and NQ data all live.", console.BOLD, console.GREEN))


if __name__ == "__main__":
    run()
