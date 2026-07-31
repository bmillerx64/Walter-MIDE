"""Official market-data provider adapters.

This module is the only place that knows how Walter's legacy Alpaca client or
Webull streaming transport satisfies :class:`MarketDataProvider`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable

from .alpaca import AlpacaClient
from .market_data import EventHandler, EventType, MarketDataProvider, MarketEvent, Subscription


class _UnsupportedSubscription(Subscription):
    def __init__(self, provider: str):
        self.provider = provider

    def add(self, symbols: Iterable[str]) -> None:
        raise NotImplementedError(f"{self.provider} streaming is not configured")

    def close(self) -> None:
        return None


class AlpacaProvider(MarketDataProvider):
    """Backward-compatible fallback around the proven Alpaca REST client."""

    provider_name = AlpacaClient.provider_name

    def __init__(self, api_key: str | None = None, secret_key: str | None = None,
                 *, client: AlpacaClient | None = None, **kwargs):
        self.client = client or AlpacaClient(api_key or "", secret_key or "", **kwargs)

    def __getattr__(self, name):
        # Discovery, bars, diagnostics, and free-float APIs remain operational
        # while callers migrate to the provider contract.
        return getattr(self.client, name)

    @property
    def diagnostics(self):
        return self.client.diagnostics

    @property
    def warnings(self):
        return self.client.warnings

    def quotes(self, symbols: Iterable[str]) -> dict:
        return {
            symbol: snapshot.get("latestQuote", {})
            for symbol, snapshot in self.snapshots(symbols).items()
        }

    def trades(self, symbols: Iterable[str]) -> dict[str, float]:
        return self.client.latest_trades(symbols)

    def latest_trades(self, symbols: Iterable[str]) -> dict[str, float]:
        return self.trades(symbols)

    def news(self, start: datetime, limit: int = 200, **kwargs) -> list[dict]:
        return self.client.news(start, limit, **kwargs)

    def snapshots(self, symbols: Iterable[str]) -> dict:
        return self.client.snapshots(symbols)

    def subscribe(self, symbols: Iterable[str], event_types: Iterable[EventType],
                  handler: EventHandler) -> Subscription:
        # Walter's existing REST fallback stays explicit; no second streaming
        # implementation is silently introduced under the Alpaca adapter.
        return _UnsupportedSubscription(self.provider_name)


class _WebullSubscription(Subscription):
    def __init__(self, transport, symbols: Iterable[str]):
        self.transport = transport
        self.transport.connect()
        self.add(symbols)

    def add(self, symbols: Iterable[str]) -> None:
        wanted = list(symbols)
        if wanted:
            self.transport.subscribe(wanted)

    def close(self) -> None:
        self.transport.close()


class WebullProvider(MarketDataProvider):
    """Webull OpenAPI adapter with streaming isolated behind the common contract.

    ``rest_client`` is the approved official SDK client. ``stream_factory``
    receives an event callback and returns the authenticated MQTT transport.
    Neither may use consumer endpoints.
    """

    provider_name = "Webull OpenAPI"

    def __init__(self, *, rest_client=None, stream_factory: Callable | None = None):
        self.rest_client = rest_client
        self.stream_factory = stream_factory

    def _rest(self, operation: str, *args, **kwargs):
        if self.rest_client is None:
            raise RuntimeError("Webull official REST client is not configured")
        method = getattr(self.rest_client, operation, None)
        if method is None:
            raise NotImplementedError(f"Webull SDK adapter does not implement {operation}")
        return method(*args, **kwargs)

    def quotes(self, symbols: Iterable[str]) -> dict:
        return self._rest("quotes", list(symbols))

    def trades(self, symbols: Iterable[str]) -> dict[str, float]:
        return self._rest("trades", list(symbols))

    def news(self, start: datetime, limit: int = 200, **kwargs) -> list[dict]:
        return self._rest("news", start, limit=limit, **kwargs)

    def snapshots(self, symbols: Iterable[str]) -> dict:
        return self._rest("snapshots", list(symbols))

    def subscribe(self, symbols: Iterable[str], event_types: Iterable[EventType],
                  handler: EventHandler) -> Subscription:
        types = set(event_types)
        if not types:
            raise ValueError("at least one streaming event type is required")
        if self.stream_factory is None:
            raise RuntimeError("Webull OpenAPI streaming bootstrap is not configured")

        def receive(event: MarketEvent) -> None:
            if event.type in types:
                handler(event)

        return _WebullSubscription(self.stream_factory(receive), symbols)
