from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs540_news_corroborated_shadow_rvol as gs540
from mide.news_provider import NewsArticle

UTC = timezone.utc


class Client:
    provider_name = "Live Webull"

    def __init__(self, rows):
        self.diagnostics = {
            "webull_native_discovery": {
                "shadow_discovery": {
                    "relative_volume_page2": {
                        "status": "PASS",
                        "rows": list(rows),
                        "admitted_to_discovery": False,
                    }
                }
            }
        }


def _hcti_shadow():
    return {
        "rank": 37,
        "symbol": "HCTI",
        "price": 0.8647,
        "change_ratio": 0.108164,
        "relative_volume_10d": 2.7891,
        "market_value": 39_380_000,
    }


def _article(now, *, headline=None):
    return NewsArticle(
        id="hcti-story",
        headline=headline or (
            "Healthcare Triangle Signs Letter of Intent to Pursue "
            "the Proposed Acquisition of Roboticom"
        ),
        created_at=now - timedelta(hours=4),
        updated_at=None,
        symbols=["HCTI"],
        source="PR Newswire",
        url="https://example.invalid/hcti",
        provider="Financial Modeling Prep",
    )


def test_sept23_hcti_shadow_rvol_plus_material_news_enters_discovery():
    now = datetime(2026, 9, 23, 13, 22, 42, tzinfo=UTC)
    client = Client([_hcti_shadow()])
    requested = {}

    def fetcher(symbols, current):
        requested["symbols"] = list(symbols)
        requested["current"] = current
        return [_article(now)]

    seeds, reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
        client,
        ["OTHER"],
        {"OTHER": ["native"]},
        now=now,
        fetcher=fetcher,
    )

    assert requested["symbols"] == ["HCTI"]
    assert seeds == ["OTHER", "HCTI"]
    assert any("material news + Webull shadow RVOL corroboration" in reason for reason in reasons["HCTI"])
    assert trace["symbols_added"] == ["HCTI"]
    assert trace["material_corroborations"][0]["shadow_rvol_rank"] == 37
    assert trace["material_corroborations"][0]["shadow_rvol_10d"] == 2.7891
    assert trace["material_corroborations"][0]["news_source"] == "PR Newswire"
    assert trace["material_corroborations"][0]["news_published_at"].startswith("2026-09-23T09:22:42")
    assert trace["trading_authority_changed"] is False


def test_shadow_rvol_without_material_news_remains_shadow_only():
    now = datetime(2026, 9, 23, 13, 22, 42, tzinfo=UTC)
    client = Client([_hcti_shadow()])

    def fetcher(symbols, current):
        return [_article(now, headline="Healthcare Triangle schedules conference presentation")]

    seeds, reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
        client, [], {}, now=now, fetcher=fetcher
    )

    assert seeds == []
    assert reasons == {}
    assert trace["symbols_added"] == []
    assert trace["material_corroborations"] == []


def test_already_discovered_symbol_gets_corroboration_reason_without_duplicate():
    now = datetime(2026, 9, 23, 13, 22, 42, tzinfo=UTC)
    client = Client([_hcti_shadow()])

    seeds, reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
        client,
        ["HCTI"],
        {"HCTI": ["Webull universe"]},
        now=now,
        fetcher=lambda symbols, current: [_article(now)],
    )

    assert seeds == ["HCTI"]
    assert len(reasons["HCTI"]) == 2
    assert trace["symbols_added"] == []
    assert len(trace["material_corroborations"]) == 1


def test_negative_or_weak_shadow_rows_are_not_targeted():
    client = Client([
        {**_hcti_shadow(), "symbol": "LOW", "relative_volume_10d": 1.9},
        {**_hcti_shadow(), "symbol": "DOWN", "change_ratio": -1.0},
    ])
    called = {"value": False}

    def fetcher(symbols, current):
        called["value"] = True
        return []

    seeds, reasons, trace = gs540.merge_news_corroborated_shadow_rvol(
        client, [], {}, fetcher=fetcher
    )

    assert seeds == []
    assert called["value"] is False
    assert trace["eligible_shadow_symbols"] == []


def test_scope_lock_is_identity_discovery_only():
    source = Path("mide/gs540_news_corroborated_shadow_rvol.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "participation_surge_score =",
        "expansion_score =",
        "expansion_quality =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL" in source
