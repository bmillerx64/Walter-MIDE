"""Provider-neutral market-data contracts consumed by Walter's pipeline.

Provider payloads remain dictionaries for backward compatibility, but provider
selection, transport lifecycle, and streaming events terminate at this boundary.
The indicator, conviction, and alert layers consume only the normalized records
produced downstream and never import a vendor adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable


class EventType(str, Enum):
    QUOTE = "quote"
    TRADE = "trade"
    SNAPSHOT = "snapshot"
    NEWS = "news"


@dataclass(frozen=True)
class MarketEvent:
    provider: str
    type: EventType
    symbol: str
    source_timestamp_ms: int
    payload: dict
    sequence: int | None = None
    wire_bytes: int = 0


EventHandler = Callable[[MarketEvent], None]


class Subscription(ABC):
    """A live subscription that may be grown without replacing its connection."""

    @abstractmethod
    def add(self, symbols: Iterable[str]) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


class MarketDataProvider(ABC):
    """Complete vendor boundary for Walter's market intelligence inputs."""

    provider_name: str

    @abstractmethod
    def quotes(self, symbols: Iterable[str]) -> dict: ...

    @abstractmethod
    def trades(self, symbols: Iterable[str]) -> dict[str, float]: ...

    @abstractmethod
    def news(self, start: datetime, limit: int = 200, **kwargs) -> list[dict]: ...

    @abstractmethod
    def snapshots(self, symbols: Iterable[str]) -> dict: ...

    @abstractmethod
    def subscribe(
        self,
        symbols: Iterable[str],
        event_types: Iterable[EventType],
        handler: EventHandler,
    ) -> Subscription: ...
