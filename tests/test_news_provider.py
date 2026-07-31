from datetime import datetime, timezone
import json
from pathlib import Path

from mide.discovery import build_seed_symbols
from mide.news_provider import (
    NewsArticle,
    NewsProvider,
    NewsService,
    symbol_news_evidence,
    ticker_inspection,
)

UTC = timezone.utc
FIXTURE = Path(__file__).parent / "fixtures" / "cycu_news.json"


class FixtureProvider(NewsProvider):
    name = "Fixture"

    def __init__(self, articles, fail=False):
        self.articles = articles
        self.fail = fail
        self.calls = []

    def fetch(self, *, since, symbols=()):
        self.calls.append((since, list(symbols)))
        if self.fail:
            raise RuntimeError("provider unavailable")
        wanted = set(symbols)
        return [
            NewsArticle(
                id=item["id"],
                headline=item["headline"],
                created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                updated_at=(datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00")) if item["updated_at"] else None),
                symbols=item["symbols"],
                source=item["source"],
                url=item["url"],
                provider=item["provider"],
            )
            for item in self.articles
            if not wanted or wanted.intersection(item["symbols"])
        ]


class DiscoveryClient:
    def __init__(self):
        self.diagnostics = {}
        self.warnings = []

    def movers(self, top):
        return []

    def most_actives(self, top):
        return []

    def assets(self):
        return []

    def public_symbol_fallback(self):
        return []


class Settings:
    max_seed_symbols = 1


def fixture():
    return json.loads(FIXTURE.read_text())


def test_universe_uses_every_asset_without_rotation_or_batch_limit():
    client = DiscoveryClient()
    client.assets = lambda: [
        {"symbol": "ZZZ", "tradable": True, "status": "active", "class": "us_equity"},
        {"symbol": "AAA", "tradable": True, "status": "active", "class": "us_equity"},
    ]
    first, provenance = build_seed_symbols(client, Settings(), [])
    second, _ = build_seed_symbols(client, Settings(), [])
    assert first == second == ["AAA", "ZZZ"]
    assert provenance == {"AAA": ["Alpaca assets"], "ZZZ": ["Alpaca assets"]}


def test_universe_uses_only_alpaca_common_stock_assets():
    client = DiscoveryClient()
    client.movers = lambda top: (_ for _ in ()).throw(AssertionError("movers called"))
    client.most_actives = lambda top: (_ for _ in ()).throw(AssertionError("actives called"))
    client.public_symbol_fallback = lambda: (_ for _ in ()).throw(
        AssertionError("fallback called")
    )
    client.assets = lambda: [
        {"symbol": "COMMON", "name": "Example Common Stock", "tradable": True,
         "status": "active", "class": "us_equity"},
        {"symbol": "WARRANT", "name": "Example Warrants", "tradable": True,
         "status": "active", "class": "us_equity"},
        {"symbol": "INACTIVE", "name": "Inactive Common Stock", "tradable": True,
         "status": "inactive", "class": "us_equity"},
    ]

    seeds, _ = build_seed_symbols(client, Settings(), [])

    assert seeds == ["COMMON"]
    assert client.diagnostics["final_seed_count"] == 1


def test_cycu_targeted_news_is_not_lost_when_global_batch_is_full(tmp_path):
    data = fixture()
    # Simulate a crowded unrelated global response, then a ticker-targeted lookup.
    provider = FixtureProvider(data["articles"])
    now = lambda: datetime(2026, 7, 30, 14, tzinfo=UTC)
    service = NewsService([provider], state_path=tmp_path / "news.json", now=now)

    service.fetch()  # global acquisition can contain any volume/order
    items = service.fetch(symbols=["CYCU"], force_lookback=True)
    seeds, reasons = build_seed_symbols(DiscoveryClient(), Settings(), items)

    # Catalyst retrieval is downstream evidence and cannot introduce CYCU into
    # the universe when no approved discovery source selected it.
    assert "CYCU" not in seeds
    assert "CYCU" not in reasons
    assert len(symbol_news_evidence(items)["CYCU"]["articles"]) == 2
    assert symbol_news_evidence(items)["CYCU"]["distinct_source_count"] == 2
    assert provider.calls[-1][1] == ["CYCU"]


def test_provider_failure_falls_back_and_is_auditable(tmp_path):
    data = fixture()
    failed = FixtureProvider([], fail=True)
    fallback = FixtureProvider(data["articles"])
    fallback.name = "Fallback"
    service = NewsService(
        [failed, fallback],
        state_path=tmp_path / "news.json",
        now=lambda: datetime(2026, 7, 30, 14, tzinfo=UTC),
    )

    items = service.fetch(symbols=["CYCU"])

    assert len(items) == 2
    assert service.metrics["provider_failures"] == 1
    assert service.metrics["active_provider"] == "Fallback"
    assert service.metrics["requests_made"] == 2


def test_ticker_inspector_retains_exact_downstream_reason():
    data = fixture()
    report = ticker_inspection(
        "CYCU",
        news_items=data["articles"],
        provider="Fixture",
        discovery_reasons={"CYCU": ["recent news"]},
        stage2_rejections=[],
        prefilter_rejections=[{"symbol": "CYCU", "reason": "Spread: 9.00% exceeds 8.00%"}],
        candidates=[],
        analyzed=[],
        records=[],
    )

    assert report["articles_returned"] == 2
    assert report["raw_provider_symbol_tags"] == [["CYCU"], ["CYCU"]]
    assert report["entered_discovery"] is True
    assert report["snapshot_prefilter_result"] == "Spread: 9.00% exceeds 8.00%"
    assert report["rejection_reason"] == "Spread: 9.00% exceeds 8.00%"
