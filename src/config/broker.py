"""Broker (ProjectX / TopstepX Gateway) configuration.

Endpoints are committed settings; credentials are secrets pulled from .env
and are never committed.
"""

import os

# --- settings (committed) --------------------------------------------------
API_BASE = "https://api.topstepx.com"
USER_HUB = "https://rtc.topstepx.com/hubs/user"
MARKET_HUB = "https://rtc.topstepx.com/hubs/market"

# --- secrets (from .env, never committed) ---------------------------------
USERNAME = os.getenv("PROJECTX_USERNAME", "")
API_KEY = os.getenv("PROJECTX_API_KEY", "")
TOKEN = os.getenv("PROJECTX_TOKEN") or None
