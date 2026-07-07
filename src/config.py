"""Application configuration loaded from the environment / .env file.

One job: read settings (credentials, endpoints) from one place so no other
module touches os.environ or hardcodes a URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # read .env at import time; real secrets stay out of git


@dataclass(frozen=True)
class Settings:
    username: str
    api_key: str
    token: str | None
    api_base: str
    user_hub: str
    market_hub: str


def get_settings() -> Settings:
    """Build Settings from environment variables (populated from .env)."""
    return Settings(
        username=os.environ.get("PROJECTX_USERNAME", ""),
        api_key=os.environ.get("PROJECTX_API_KEY", ""),
        token=os.environ.get("PROJECTX_TOKEN") or None,
        api_base=os.environ.get("PROJECTX_API_BASE", "https://api.topstepx.com"),
        user_hub=os.environ.get("PROJECTX_USER_HUB", "https://rtc.topstepx.com/hubs/user"),
        market_hub=os.environ.get("PROJECTX_MARKET_HUB", "https://rtc.topstepx.com/hubs/market"),
    )
