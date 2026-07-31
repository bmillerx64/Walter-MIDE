"""Provider-neutral, failure-tolerant news acquisition and coverage evidence."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable
import json
import re

from .resilience import record_provider_failure


UTC = timezone.utc
DEFAULT_STATE_PATH = Path("data/news_provider_state.json")


def _utc(value, default=None) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return default
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _headline_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class NewsArticle:
    id: str
    headline: str
    created_at: datetime
    updated_at: datetime | None
    symbols: list[str]
    source: str
    url: str | None
    provider: str

    def as_dict(self) -> dict:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return result


class NewsProvider(ABC):
    """Contract implemented only by official, credentialed provider APIs."""

    name: str

    @abstractmethod
    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        """Return every available article updated after ``since``."""


class AlpacaNewsProvider(NewsProvider):
    """Temporary fallback using Alpaca's official Market Data news endpoint."""

    name = "Alpaca (temporary fallback)"

    def __init__(self, client, *, page_budget: int = 20):
        self.client = client
        self.page_budget = page_budget
        self.request_count = 0
        self.provider_label = "Alpaca"

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        wanted = sorted(set(symbols))
        batches = [wanted[index:index + 50] for index in range(0, len(wanted), 50)] or [[]]
        raw = []
        self.request_count = 0
        for batch in batches:
            self.request_count += 1
            raw.extend(self.client.news(
                since,
                limit=self.page_budget * self.client.NEWS_MAX_LIMIT,
                symbols=batch or None,
                sort="asc",
            ))
        return [article for item in raw if (article := self._normalize(item))]

    def _normalize(self, item: dict) -> NewsArticle | None:
        created = _utc(item.get("created_at") or item.get("updated_at"))
        headline = str(item.get("headline") or "").strip()
        if created is None or not headline:
            return None
        symbols = sorted({str(s).strip().upper() for s in item.get("symbols", []) if str(s).strip()})
        return NewsArticle(
            id=str(item.get("id") or f"headline:{_headline_key(headline)}"),
            headline=headline,
            created_at=created,
            updated_at=_utc(item.get("updated_at")),
            symbols=symbols,
            source=str(item.get("source") or item.get("author") or "Unknown").strip(),
            url=item.get("url") or None,
            provider=self.provider_label,
        )


class MarketDataNewsProvider(AlpacaNewsProvider):
    """Normalize news obtained through the provider-neutral market-data seam."""

    def __init__(self, provider, *, page_budget: int = 20):
        super().__init__(provider, page_budget=page_budget)
        self.provider_label = getattr(provider, "provider_name", provider.__class__.__name__)
        self.name = f"{self.provider_label} news"

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        # Provider implementations own vendor paging and request limits.
        raw = self.client.news(since, limit=self.page_budget * 50,
                               symbols=sorted(set(symbols)) or None, sort="asc")
        return [article for item in raw if (article := self._normalize(item))]


class CredentialPendingNewsProvider(NewsProvider):
    """Explicit non-activation guard for enterprise providers under evaluation."""

    def __init__(self, name: str):
        self.name = name

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        raise RuntimeError(f"{self.name} is not activated: official credentials and permitted usage are required")


class UnavailableNewsProvider(NewsProvider):
    """Explicit provider seam when the selected market-data API has no news feed."""

    def __init__(self, name: str, reason: str):
        self.name, self.reason = name, reason

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        # An empty result keeps scanning operational without silently contacting
        # another market-data vendor. Diagnostics retain the missing capability.
        return []


class NewsService:
    """Incremental cache, deduplication, metrics, and safe provider fallback."""

    def __init__(self, providers: Iterable[NewsProvider], *, state_path=DEFAULT_STATE_PATH, now=None):
        self.providers = list(providers)
        self.state_path = Path(state_path)
        self.now = now or (lambda: datetime.now(UTC))
        self._state = self._load()
        self.metrics = {
            "active_provider": "None",
            "last_successful_fetch": self._state.get("last_successful_fetch"),
            "requests_made": 0,
            "articles_received": 0,
            "unique_symbols_discovered": 0,
            "provider_failures": 0,
            "articles_without_symbols": 0,
            "request_latency_ms": [],
        }

    def _load(self) -> dict:
        try:
            value = json.loads(self.state_path.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, articles: list[NewsArticle], fetched_at: datetime) -> None:
        payload = {
            "last_successful_fetch": fetched_at.isoformat(),
            "articles": [a.as_dict() for a in articles],
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")))
        temporary.replace(self.state_path)
        self._state = payload

    def _cached(self) -> list[NewsArticle]:
        output = []
        for item in self._state.get("articles", []):
            created = _utc(item.get("created_at"))
            if created is None:
                continue
            output.append(NewsArticle(
                id=str(item.get("id")), headline=str(item.get("headline", "")), created_at=created,
                updated_at=_utc(item.get("updated_at")), symbols=list(item.get("symbols") or []),
                source=str(item.get("source") or "Unknown"), url=item.get("url"),
                provider=str(item.get("provider") or "Unknown"),
            ))
        return output

    def fetch(
        self,
        *,
        symbols: Iterable[str] = (),
        initial_lookback=timedelta(days=3),
        force_lookback: bool = False,
    ) -> list[dict]:
        cached = self._cached()
        prior = _utc(self._state.get("last_successful_fetch"))
        # A small overlap protects articles updated at the exact cursor boundary.
        since = (
            self.now() - initial_lookback
            if force_lookback
            else (prior - timedelta(minutes=2)) if prior else self.now() - initial_lookback
        )
        requested_symbols = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
        fresh: list[NewsArticle] = []
        for provider in self.providers:
            started = perf_counter()
            try:
                fresh = provider.fetch(since=since, symbols=requested_symbols)
                if not isinstance(fresh, list) or any(
                    not isinstance(article, NewsArticle) for article in fresh
                ):
                    raise ValueError("provider returned malformed news response")
            except Exception as exc:
                self.metrics["provider_failures"] += 1
                self.metrics.setdefault("failure_details", []).append(f"{provider.name}: {exc}")
                record_provider_failure(
                    self.metrics, provider=provider.name, operation="fetch news",
                    exception=exc, affected_symbols=requested_symbols,
                    recovery_action="try next provider; preserve cached news",
                )
                continue
            finally:
                self.metrics["requests_made"] += max(1, int(getattr(provider, "request_count", 1)))
                self.metrics["request_latency_ms"].append(round((perf_counter() - started) * 1000, 1))
            self.metrics["active_provider"] = provider.name
            break

        combined = self._deduplicate([*cached, *fresh])
        self.metrics["articles_received"] += len(fresh)
        self.metrics["articles_without_symbols"] += sum(not article.symbols for article in fresh)
        self.metrics["unique_symbols_discovered"] = len({s for article in combined for s in article.symbols})
        if fresh:
            fetched_at = self.now()
            self.metrics["last_successful_fetch"] = fetched_at.isoformat()
            try:
                self._save(combined, fetched_at)
            except OSError as exc:
                self.metrics.setdefault("failure_details", []).append(f"cache write: {exc}")
        return [article.as_dict() for article in combined]

    @staticmethod
    def _deduplicate(articles: Iterable[NewsArticle]) -> list[NewsArticle]:
        by_id: dict[tuple[str, str], NewsArticle] = {}
        headline_seen: set[tuple[str, str]] = set()
        for article in sorted(articles, key=lambda a: a.updated_at or a.created_at):
            provider_id = (article.provider.casefold(), article.id)
            headline_id = (article.provider.casefold(), _headline_key(article.headline))
            if provider_id in by_id or headline_id in headline_seen:
                continue
            by_id[provider_id] = article
            headline_seen.add(headline_id)
        return sorted(by_id.values(), key=lambda a: a.created_at, reverse=True)


def symbol_news_evidence(news_items: Iterable[dict]) -> dict[str, dict]:
    """Retain every article and compute corroboration without changing ranking."""
    output: dict[str, dict] = {}
    for article in news_items:
        seen = _utc(article.get("created_at") or article.get("updated_at"))
        if seen is None:
            continue
        for raw in article.get("symbols") or []:
            symbol = str(raw).strip().upper()
            if not symbol:
                continue
            evidence = output.setdefault(symbol, {"articles": [], "sources": set(), "first_seen": seen, "latest_corroboration": seen})
            evidence["articles"].append(article)
            evidence["sources"].add(str(article.get("source") or "Unknown"))
            evidence["first_seen"] = min(evidence["first_seen"], seen)
            evidence["latest_corroboration"] = max(evidence["latest_corroboration"], seen)
    for evidence in output.values():
        evidence["article_count"] = len(evidence["articles"])
        evidence["distinct_source_count"] = len(evidence.pop("sources"))
        evidence["first_seen"] = evidence["first_seen"].isoformat()
        evidence["latest_corroboration"] = evidence["latest_corroboration"].isoformat()
    return output


def ticker_inspection(
    symbol: str,
    *,
    news_items,
    provider: str,
    discovery_reasons,
    stage2_rejections,
    prefilter_rejections,
    candidates,
    analyzed,
    records,
) -> dict:
    """Explain one ticker's complete news-to-final-disposition path."""
    symbol = str(symbol or "").strip().upper()
    articles = [item for item in news_items or [] if symbol in {str(s).upper() for s in item.get("symbols") or []}]
    stage2 = next((item for item in stage2_rejections or [] if item.get("symbol") == symbol), None)
    prefilter = next((item for item in prefilter_rejections or [] if item.get("symbol") == symbol), None)
    candidate_symbols = [item.get("symbol") for item in candidates or []]
    record = next((item for item in records or [] if item.get("symbol") == symbol), None)
    analyzed_record = next((item for item in analyzed or [] if item.get("symbol") == symbol), None)
    return {
        "ticker": symbol,
        "provider_queried": provider,
        "articles_returned": len(articles),
        "raw_provider_symbol_tags": [item.get("symbols") or [] for item in articles],
        "entered_discovery": symbol in (discovery_reasons or {}),
        "stage_2_result": stage2.get("reason") if stage2 else ("PASS" if symbol in candidate_symbols or analyzed_record else "NOT REACHED"),
        "snapshot_prefilter_result": prefilter.get("reason") if prefilter else ("PASS" if symbol in candidate_symbols else "NOT REACHED"),
        "candidate_rank": (candidate_symbols.index(symbol) + 1) if symbol in candidate_symbols else None,
        "bar_availability": "available" if analyzed_record else "unavailable/not requested",
        "final_disposition": (record or {}).get("final_decision") or (record or {}).get("candidate_status") or "Not analyzed",
        "rejection_reason": (record or {}).get("rejection_reason") or (stage2 or {}).get("reason") or (prefilter or {}).get("reason"),
    }
