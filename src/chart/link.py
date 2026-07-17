"""Build a chart URL. One job, because two doors now need the same one.

``src.cli.chart`` opens the chart it just served; ``src.cli.explore_session``
opens the chart someone else is already serving. Both must agree on what a deep
link looks like, and a second opinion about the query string is a link that
silently opens the wrong bar.

The frontend's side of this contract is ``deepLink()`` in
``frontend/chart/js/main.js``: `at` in epoch seconds, optional `symbol` and
`tf`, and anything unparseable opens the chart normally rather than failing.
"""

from __future__ import annotations

import socket
from urllib.parse import urlencode

from src.config import chart as cfg


def base_url(host: str | None = None, port: int | None = None) -> str:
    return f"http://{host or cfg.HOST}:{port or cfg.PORT}"


def deep_link(base: str, symbol: str, timeframe: str, at: int) -> str:
    """The URL that boots straight into replay at ``at`` (epoch seconds)."""
    query = urlencode({"symbol": symbol, "tf": timeframe, "at": int(at)})
    return f"{base.rstrip('/')}/?{query}"


def is_serving(host: str | None = None, port: int | None = None,
               timeout: float = 0.4) -> bool:
    """Is something listening? Asked before opening a browser at it.

    A tab that cannot connect is a worse failure than a sentence saying the
    server is down: the browser blames the network, the user blames the link,
    and the actual cause - no server - is the one thing the page cannot say.
    """
    try:
        with socket.create_connection((host or cfg.HOST, port or cfg.PORT), timeout):
            return True
    except OSError:
        return False
