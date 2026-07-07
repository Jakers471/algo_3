"""Configuration package: settings sectioned by area.

The .env file is loaded exactly once here, at the package front door, so
every section can read secrets via ``os.getenv()`` without repeating it.
Import only the section you need, e.g. ``from src.config import broker``.
"""

from dotenv import load_dotenv

load_dotenv()  # single load point for secrets; never commit .env
