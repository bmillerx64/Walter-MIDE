"""GS544: Alpaca news coverage is observed without trading authority."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide.authorities import discovery_news


UTC = timezone.utc
NOW = datetime(2026, 9, 24, 18, 17, tzinfo=UTC)


class FakeAlpaca:
    provider_name = "Alpaca Market Data"

    def __init__(self):
        self.calls = []

    def news(self, start, limit=200, *, symbols=None, sort="asc"):
        requested = list(symbols or [])
        self.calls.append(
            {
                "start": start,
                "limit": limit,
                "symbols": requested,
                "sort": sort,
            }
        )
        rows = []
        for symbol in requested:
            rows.append(
                {
                    "id": f"{symbol}-news",
                    "headline": (
                        f"{symbol} reports record revenue and earnings beat"
                    ),
                    "created_at": (NOW - timedelta(hours=4)).isoformat(),
                    "updated_at": (NOW - timedelta(hours=4)).isoformat(),
                    "symbols": [symbol],
                    "source": "Benzinga",
                    "url": f"https://example.test/{symbol}",
                }
            )
        return rows


class FakeLiveClient:
    def __init__(self):
        self._universe_client = FakeAlpaca()
        self.diagnostics = {}


def primary_article(symbol: str) -> dict:
    return {
        "id": f"primary-{symbol}",
        "headline": f"{symbol} primary article",
        "created_at": (NOW - timedelta(minutes=10)).isoformat(),
        "symbols": [symbol],
        "source": "Reuters",
        "provider": "Financial Modeling Prep",
    }


def test_gs544_queries_only_symbols_missing_from_active_news():
    client = FakeLiveClient()

    trace = discovery_news.observe_alpaca_news_shadow(
        client,
        ["DDC", "RAVE"],
        [primary_article("DDC")],
        now=NOW,
    )

    assert trace["authority"] == "NEWS_COVERAGE_OBSERVATION_ONLY"
    assert trace["primary_covered_symbols"] == ["DDC"]
    assert trace["requested_missing_symbols"] == ["RAVE"]
    assert trace["query_targets"] == ["RAVE"]
    assert trace["request_made"] is True
    assert trace["found_symbols"] == ["RAVE"]
    assert trace["missing_after_shadow"] == []
    assert trace["coverage_gain_count"] == 1
    assert trace["articles_by_symbol"]["RAVE"]["source"] == "Benzinga"
    assert "earnings beat" in trace["articles_by_symbol"]["RAVE"]["headline"]
    assert trace["trading_authority_changed"] is False
    assert trace["headline_changed"] is False
    assert trace["catalyst_score_changed"] is False
    assert client._universe_client.calls[0]["symbols"] == ["RAVE"]


def test_gs544_reuses_bounded_shadow_cache_inside_five_minutes():
    client = FakeLiveClient()

    first = discovery_news.observe_alpaca_news_shadow(
        client,
        ["RAVE"],
        [],
        now=NOW,
    )
    second = discovery_news.observe_alpaca_news_shadow(
        client,
        ["RAVE"],
        [],
        now=NOW + timedelta(minutes=1),
    )

    assert first["request_made"] is True
    assert second["request_made"] is False
    assert second["cache_reused"] is True
    assert second["found_symbols"] == ["RAVE"]
    assert len(client._universe_client.calls) == 1


def test_gs544_newly_missing_symbol_is_checked_without_waiting_for_refresh():
    client = FakeLiveClient()

    discovery_news.observe_alpaca_news_shadow(
        client,
        ["RAVE"],
        [],
        now=NOW,
    )
    trace = discovery_news.observe_alpaca_news_shadow(
        client,
        ["NEW", "RAVE"],
        [],
        now=NOW + timedelta(minutes=1),
    )

    assert trace["query_targets"] == ["NEW"]
    assert trace["found_symbols"] == ["NEW", "RAVE"]
    assert len(client._universe_client.calls) == 2
    assert client._universe_client.calls[-1]["symbols"] == ["NEW"]


def test_gs544_shadow_failure_is_diagnostic_only():
    class BrokenAlpaca:
        provider_name = "Alpaca Market Data"

        def news(self, *_args, **_kwargs):
            raise RuntimeError("synthetic outage")

    client = FakeLiveClient()
    client._universe_client = BrokenAlpaca()

    trace = discovery_news.observe_alpaca_news_shadow(
        client,
        ["RAVE"],
        [],
        now=NOW,
    )

    assert trace["request_made"] is False
    assert "synthetic outage" in trace["reason"]
    assert trace["found_symbols"] == []
    assert trace["trading_authority_changed"] is False


def test_gs544_live_app_does_not_merge_shadow_articles_into_catalyst_input():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("# GS544: observe only")
    end = source.index("        decisions = {}", start)
    block = source[start:end]

    assert "observe_alpaca_news_shadow" in block
    assert "news_items.extend" not in block
    assert "news_items.append" not in block
    assert "indexed.update" not in block
    assert "indexed[" not in block


def test_gs544_scope_is_observation_only():
    source = (
        Path("mide/authorities/discovery_news.py")
        .read_text(encoding="utf-8")
    )
    start = source.index("# GS544 Alpaca/Benzinga shadow news coverage")
    end = source.index("# GS502 direct Benzinga breaking-news discovery", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)
