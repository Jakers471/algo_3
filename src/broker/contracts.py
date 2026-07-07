"""Contract lookup on the ProjectX Gateway API.

One job: search contracts and resolve a tradable symbol to its contract id.
Uses ProjectXClient for the connection.
"""

from __future__ import annotations

import logging

from src.broker.client import ProjectXClient

logger = logging.getLogger(__name__)


def search_contracts(client: ProjectXClient, search_text: str, live: bool = False) -> list[dict]:
    """Return contracts matching ``search_text`` (up to 20 from the API)."""
    data = client.post("/api/Contract/search", {"searchText": search_text, "live": live})
    if not data.get("success"):
        raise RuntimeError(f"Contract/search failed (errorCode={data.get('errorCode')}).")
    contracts = data.get("contracts", [])
    logger.info("Found %d contract(s) for '%s'.", len(contracts), search_text)
    return contracts


def resolve_symbol(contracts: list[dict], symbol_id: str) -> dict | None:
    """Pick the active contract whose ``symbolId`` exactly matches, else None.

    ``symbol_id`` is the root, e.g. ``F.US.ENQ`` for the E-mini Nasdaq-100
    (distinct from ``F.US.MNQ``, the Micro). Prefers the active contract.
    """
    matches = [c for c in contracts if c.get("symbolId") == symbol_id]
    if not matches:
        return None
    for contract in matches:
        if contract.get("activeContract"):
            return contract
    return matches[0]
