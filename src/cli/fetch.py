"""CLI command: fetch as much NQ history as the API will give, save as CSV.

One job: orchestration. Connect, resolve the NQ contract, page back through
every configured timeframe as far as the data goes, and save each to
data/NQ_<TF>.csv. Thin door — the real work lives in broker/ and storage/.
"""

from __future__ import annotations

import logging

from src.broker import contracts, history
from src.broker.client import ProjectXClient
from src.config import broker as broker_cfg
from src.config import data as data_cfg
from src.core import console
from src.core.logging_config import setup_logging
from src.storage import csv_store

logger = logging.getLogger(__name__)


def _header(text: str) -> None:
    logger.info(console.paint(text, console.BOLD, console.CYAN))


def run() -> None:
    setup_logging()

    _header("Connect to ProjectX")
    client = ProjectXClient(
        base_url=broker_cfg.API_BASE,
        username=broker_cfg.USERNAME,
        api_key=broker_cfg.API_KEY,
        token=broker_cfg.TOKEN,
    )
    client.connect()

    _header("Resolve NQ contract")
    found = contracts.search_contracts(client, data_cfg.DEFAULT_SYMBOL_SEARCH)
    contract = contracts.resolve_symbol(found, data_cfg.DEFAULT_SYMBOL_ID)
    if not contract:
        logger.error("Could not resolve NQ contract (%s).", data_cfg.DEFAULT_SYMBOL_ID)
        return
    contract_id = contract["id"]
    logger.info(
        "Contract: %s  %s",
        console.paint(contract_id, console.BOLD, console.GREEN),
        console.paint(contract.get("description", ""), console.DIM),
    )

    _header("Fetch & save every timeframe (as far back as available)")
    summary: list[tuple[str, int, str, str, str]] = []
    for tf in data_cfg.FETCH_TIMEFRAMES:
        if tf not in history.TIMEFRAMES:
            logger.warning("Unknown timeframe '%s' - skipping.", tf)
            continue
        unit, unit_number = history.TIMEFRAMES[tf]
        logger.info(console.paint(f"-- {tf} --", console.BOLD))
        bars = history.retrieve_history(client, contract_id, unit=unit, unit_number=unit_number)
        if not bars:
            logger.warning("No %s bars returned.", tf)
            continue
        path = csv_store.save_bars_csv(data_cfg.DEFAULT_SYMBOL_SEARCH, tf, bars, data_cfg.DATA_DIR)
        summary.append((tf, len(bars), bars[0]["t"], bars[-1]["t"], path))

    _header("Summary")
    for tf, n, first, last, path in summary:
        logger.info(
            "  %-4s %9d bars  %s -> %s",
            tf, n,
            console.paint(first, console.DIM),
            console.paint(last, console.DIM),
        )
    logger.info(console.paint("Done.", console.BOLD, console.GREEN))


if __name__ == "__main__":
    run()
