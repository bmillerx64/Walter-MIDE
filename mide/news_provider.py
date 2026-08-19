"""Provider-neutral, failure-tolerant news acquisition and coverage evidence."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable
import json
import os
import re

import requests

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


def _configured_fmp_api_key() -> str:
    """Resolve FMP without logging or exposing the credential value."""
    for name in ("FMP_API_KEY", "FINANCIAL_MODELING_PREP_API_KEY"):
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    try:
        import streamlit as st
        for name in ("FMP_API_KEY", "FINANCIAL_MODELING_PREP_API_KEY"):
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    return ""


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
    name: str

    @abstractmethod
    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        """Return every available article updated after ``since``."""


class AlpacaNewsProvider(NewsProvider):
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
    def __init__(self, provider, *, page_budget: int = 20):
        super().__init__(provider, page_budget=page_budget)
        self.provider_label = getattr(provider, "provider_name", provider.__class__.__name__)
        self.name = f"{self.provider_label} news"

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        raw = self.client.news(since, limit=self.page_budget * 50,
                               symbols=sorted(set(symbols)) or None, sort="asc")
        return [article for item in raw if (article := self._normalize(item))]


class FMPNewsProvider(NewsProvider):
    """Official FMP stock-news and press-release adapter for catalyst evidence."""

    name = "Financial Modeling Prep news"
    BASE_URL = "https://financialmodelingprep.com/stable"
    BATCH_SIZE = 20
    FRESHNESS = timedelta(hours=6)

    def __init__(self, api_key: str, *, timeout: int = 12, session=None, now=None):
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout
        self.session = session or requests.Session()
        self.now = now or (lambda: datetime.now(UTC))
        self.request_count = 0
        # Diagnostic-only request provenance. Never includes the API key.
        self.last_since: datetime | None = None
        self.last_requested_symbols: list[str] = []
        self.endpoints_requested: list[str] = []

    @staticmethod
    def _symbols(item: dict) -> list[str]:
        raw = item.get("symbols")
        if isinstance(raw, str):
            values = re.split(r"[,\s]+", raw)
        elif isinstance(raw, (list, tuple, set)):
            values = raw
        else:
            single = item.get("symbol") or item.get("ticker")
            values = [single] if single else []
        return sorted({str(value).strip().upper() for value in values if str(value or "").strip()})

    @classmethod
    def _normalize(cls, item: dict, *, endpoint: str) -> NewsArticle | None:
        if not isinstance(item, dict):
            return None
        headline = str(item.get("title") or item.get("headline") or "").strip()
        created = _utc(
            item.get("publishedDate") or item.get("published_date")
            or item.get("date") or item.get("created_at")
        )
        symbols = cls._symbols(item)
        if not headline or created is None or not symbols:
            return None
        url = item.get("url") or item.get("link") or None
        source = str(
            item.get("publisher") or item.get("site") or item.get("source")
            or ("Company Press Release" if "press-releases" in endpoint else "FMP")
        ).strip()
        stable_id = item.get("id") or url or f"{endpoint}:{created.isoformat()}:{_headline_key(headline)}"
        return NewsArticle(
            id=str(stable_id), headline=headline, created_at=created,
            updated_at=_utc(item.get("updated_at") or item.get("updatedDate")),
            symbols=symbols, source=source or "FMP", url=str(url) if url else None,
            provider="Financial Modeling Prep",
        )

    def _request(self, endpoint: str, symbols: list[str], since: datetime) -> list[NewsArticle]:
        params = {
            "symbols": ",".join(symbols),
            "from": since.astimezone(UTC).date().isoformat(),
            "to": self.now().astimezone(UTC).date().isoformat(),
            "page": 0,
            "limit": 100,
            "apikey": self.api_key,
        }
        self.request_count += 1
        self.endpoints_requested.append(endpoint)
        response = self.session.get(
            f"{self.BASE_URL}/{endpoint}", params=params, timeout=self.timeout
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        output = []
        for item in rows:
            article = self._normalize(item, endpoint=endpoint)
            if article is not None and article.created_at >= since:
                output.append(article)
        return output

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        wanted = list(dict.fromkeys(
            str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()
        ))
        if not self.api_key:
            raise RuntimeError("FMP news credential is not configured")
        since = max(since.astimezone(UTC), self.now().astimezone(UTC) - self.FRESHNESS)
        self.last_since = since
        self.last_requested_symbols = list(wanted)
        self.endpoints_requested = []
        batches = [wanted[i:i + self.BATCH_SIZE] for i in range(0, len(wanted), self.BATCH_SIZE)] or [[]]
        self.request_count = 0
        output: list[NewsArticle] = []
        for batch in batches:
            if not batch:
                continue
            output.extend(self._request("news/stock", batch, since))
            output.extend(self._request("news/press-releases", batch, since))
        return output


class CredentialPendingNewsProvider(NewsProvider):
    def __init__(self, name: str):
        self.name = name

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        raise RuntimeError(f"{self.name} is not activated: official credentials and permitted usage are required")


class UnavailableNewsProvider(NewsProvider):
    def __init__(self, name: str, reason: str):
        self.name, self.reason = name, reason

    def fetch(self, *, since: datetime, symbols: Iterable[str] = ()) -> list[NewsArticle]:
        return []


class NewsService:
    """Incremental cache, deduplication, metrics, and safe provider fallback."""

    def __init__(self, providers: Iterable[NewsProvider], *, state_path=DEFAULT_STATE_PATH, now=None):
        configured = list(providers)
        if configured and all(isinstance(provider, UnavailableNewsProvider) for provider in configured):
            api_key = _configured_fmp_api_key()
            if api_key:
                configured.insert(0, FMPNewsProvider(api_key, now=now))
        self.providers = configured
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
            # GS284 diagnostic-only catalyst/news provenance.
            "requested_symbols": [],
            "query_since": None,
            "effective_provider_since": None,
            "provider_endpoints": [],
            "symbols_with_articles": [],
            "symbols_without_articles": [],
            "newest_articles_by_symbol": {},
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

    def _record_symbol_trace(
        self, requested_symbols: list[str], articles: list[NewsArticle]
    ) -> None:
        """Record per-symbol news freshness/classification without changing decisions."""
        from .news import MATERIAL_CATALYST_SCORE, classify_headline

        now = self.now().astimezone(UTC)
        trace: dict[str, dict] = {}
        for symbol in requested_symbols:
            matches = [article for article in articles if symbol in article.symbols]
            matches.sort(key=lambda article: article.created_at, reverse=True)
            material = []
            for article in matches:
                score, flags = classify_headline(article.headline)
                if abs(float(score)) >= MATERIAL_CATALYST_SCORE:
                    material.append((article, score, flags))
            newest = matches[0] if matches else None
            newest_score, newest_flags = (
                classify_headline(newest.headline) if newest else (0, [])
            )
            selected_material = material[0] if material else None
            trace[symbol] = {
                "articles_returned": len(matches),
                "newest_article_at": newest.created_at.isoformat() if newest else None,
                "newest_article_age_minutes": (
                    round(max(0.0, (now - newest.created_at).total_seconds()) / 60, 1)
                    if newest else None
                ),
                "newest_headline": newest.headline if newest else None,
                "newest_source": newest.source if newest else None,
                "newest_provider": newest.provider if newest else None,
                "newest_catalyst_score": newest_score if newest else None,
                "newest_catalyst_flags": list(newest_flags),
                "material_article_count": len(material),
                "selected_material_headline": (
                    selected_material[0].headline if selected_material else None
                ),
                "selected_material_at": (
                    selected_material[0].created_at.isoformat() if selected_material else None
                ),
                "selected_material_score": (
                    selected_material[1] if selected_material else None
                ),
                "selected_material_flags": (
                    list(selected_material[2]) if selected_material else []
                ),
            }
        self.metrics["newest_articles_by_symbol"] = trace
        self.metrics["symbols_with_articles"] = sorted(
            symbol for symbol, item in trace.items() if item["articles_returned"]
        )
        self.metrics["symbols_without_articles"] = sorted(
            symbol for symbol, item in trace.items() if not item["articles_returned"]
        )

    def fetch(
        self,
        *,
        symbols: Iterable[str] = (),
        initial_lookback=timedelta(days=3),
        force_lookback: bool = False,
    ) -> list[dict]:
        cached = self._cached()
        prior = _utc(self._state.get("last_successful_fetch"))
        since = (
            self.now() - initial_lookback
            if force_lookback
            else (prior - timedelta(minutes=2)) if prior else self.now() - initial_lookback
        )
        requested_symbols = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
        self.metrics["requested_symbols"] = list(requested_symbols)
        self.metrics["query_since"] = since.astimezone(UTC).isoformat()
        fresh: list[NewsArticle] = []
        active_provider = None
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
            active_provider = provider
            break

        if active_provider is not None:
            provider_since = getattr(active_provider, "last_since", None)
            self.metrics["effective_provider_since"] = (
                provider_since.astimezone(UTC).isoformat()
                if isinstance(provider_since, datetime)
                else self.metrics["query_since"]
            )
            self.metrics["provider_endpoints"] = list(
                getattr(active_provider, "endpoints_requested", []) or []
            )

        combined = self._deduplicate([*cached, *fresh])
        if self.metrics["active_provider"] == FMPNewsProvider.name:
            cutoff = self.now().astimezone(UTC) - FMPNewsProvider.FRESHNESS
            wanted = set(requested_symbols)
            combined = [
                article for article in combined
                if article.created_at >= cutoff
                and (not wanted or bool(wanted.intersection(article.symbols)))
            ]
        self.metrics["articles_received"] += len(fresh)
        self.metrics["articles_without_symbols"] += sum(not article.symbols for article in fresh)
        self.metrics["unique_symbols_discovered"] = len({s for article in combined for s in article.symbols})
        self._record_symbol_trace(requested_symbols, combined)
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
