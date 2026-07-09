"""Real-time market data over the ProjectX SignalR market hub.

One job: hold a websocket connection to the market hub, subscribe a contract's
streams, and hand every raw event to a callback. Plumbing only - it does not
interpret, store, or reshape what arrives. That belongs to whoever passes in
the callback (see capture/recorder.py).

Three streams, and they are NOT the same thing:
  GatewayTrade - executed trades: price and size. The "tick" / time-and-sales.
  GatewayQuote - top-of-book bid/ask, pushed when the QUOTE changes, not when
                 a trade happens.
  GatewayDepth - the fuller order book.

A NinjaTrader 'Last' tick row is a trade with the prevailing quote stamped on
it - i.e. GatewayTrade joined against the most recent GatewayQuote. Subscribing
to quotes alone yields a stream with no trades in it, and every volume
indicator downstream would read zero.

Reconnects resubscribe: SignalR drops subscriptions with the connection, and a
silently unsubscribed stream looks exactly like a quiet market.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from signalrcore.hub_connection_builder import HubConnectionBuilder

from src.config import live as live_cfg

logger = logging.getLogger(__name__)

# (event name, subscribe method, unsubscribe method)
TRADES = ("GatewayTrade", "SubscribeContractTrades", "UnsubscribeContractTrades")
QUOTES = ("GatewayQuote", "SubscribeContractQuotes", "UnsubscribeContractQuotes")
DEPTH = ("GatewayDepth", "SubscribeContractMarketDepth", "UnsubscribeContractMarketDepth")


def streams_from_config() -> list[tuple]:
    """The streams config/live.py asks for."""
    chosen = []
    if live_cfg.SUBSCRIBE_TRADES:
        chosen.append(TRADES)
    if live_cfg.SUBSCRIBE_QUOTES:
        chosen.append(QUOTES)
    if live_cfg.SUBSCRIBE_DEPTH:
        chosen.append(DEPTH)
    return chosen


class MarketHub:
    """A live subscription to one contract's market data."""

    def __init__(self, hub_url: str, token: str, contract_id: str,
                 streams: list[tuple] | None = None) -> None:
        self.contract_id = contract_id
        self.streams = streams if streams is not None else streams_from_config()
        self._on_event: Callable[[str, tuple], None] | None = None

        # The token goes in the query string AND the accessTokenFactory: the
        # gateway reads it from the URL when negotiation is skipped.
        url = f"{hub_url}?access_token={token}"
        self._conn = (
            HubConnectionBuilder()
            .with_url(url, options={
                "skip_negotiation": True,
                "access_token_factory": lambda: token,
            })
            .with_automatic_reconnect({
                "type": "interval",
                "keep_alive_interval": live_cfg.KEEPALIVE_INTERVAL,
                "reconnect_interval": live_cfg.RECONNECT_INTERVAL,
                "max_attempts": live_cfg.RECONNECT_ATTEMPTS,
            })
            .build()
        )

    def on_event(self, handler: Callable[[str, tuple], None]) -> None:
        """Register the sink. Called as ``handler(event_name, raw_args)``."""
        self._on_event = handler

    def start(self) -> None:
        """Connect, then subscribe. Resubscribes on every reconnect."""
        for event_name, _, _ in self.streams:
            self._conn.on(event_name, self._make_dispatch(event_name))

        self._conn.on_open(self._on_open)
        self._conn.on_close(lambda: logger.warning("Market hub: connection closed"))
        self._conn.on_error(lambda data: logger.error("Market hub error: %s", data))

        logger.info("Market hub: connecting (%s)", self.contract_id)
        self._conn.start()

    def _make_dispatch(self, event_name: str):
        def dispatch(args):
            if self._on_event is not None:
                self._on_event(event_name, args)
        return dispatch

    def _on_open(self) -> None:
        # Fires on first connect AND after each automatic reconnect, which is
        # exactly when subscriptions need re-establishing.
        logger.info("Market hub: open - subscribing %d stream(s)", len(self.streams))
        for event_name, subscribe, _ in self.streams:
            self._conn.send(subscribe, [self.contract_id])
            logger.info("  subscribed %s -> %s", self.contract_id, event_name)

    def stop(self) -> None:
        """Unsubscribe and close. Best-effort: a dead socket cannot unsubscribe."""
        for _, _, unsubscribe in self.streams:
            try:
                self._conn.send(unsubscribe, [self.contract_id])
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise
                logger.debug("Unsubscribe %s failed (socket likely gone): %s", unsubscribe, exc)
        self._conn.stop()
        logger.info("Market hub: stopped")
