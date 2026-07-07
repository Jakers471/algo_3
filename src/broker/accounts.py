"""Account lookup on the ProjectX Gateway API.

One job: search accounts and pick a tradable one. Uses ProjectXClient for
the connection; holds no session state of its own.
"""

from __future__ import annotations

import logging

from src.broker.client import ProjectXClient

logger = logging.getLogger(__name__)


def search_accounts(client: ProjectXClient, only_active: bool = True) -> list[dict]:
    """Return the list of accounts (optionally only active ones)."""
    data = client.post("/api/Account/search", {"onlyActiveAccounts": only_active})
    if not data.get("success"):
        raise RuntimeError(f"Account/search failed (errorCode={data.get('errorCode')}).")
    accounts = data.get("accounts", [])
    logger.info("Found %d account(s).", len(accounts))
    return accounts


def select_tradable(accounts: list[dict]) -> dict | None:
    """Pick the first account that can trade, else the first account."""
    if not accounts:
        return None
    for acct in accounts:
        if acct.get("canTrade"):
            return acct
    return accounts[0]
