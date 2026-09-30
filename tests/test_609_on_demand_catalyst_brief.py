from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide.authorities import discovery_news, presentation_audio
from mide.news_provider import NewsArticle


UTC = timezone.utc
NOW = datetime(2026, 9, 30, 12, 30, tzinfo=UTC)


def article(article_id, headline, minutes_ago, *, symbol="CNTB", source="Benzinga", provider="Benzinga"):
    return NewsArticle(
        id=article_id,
        headline=headline,
        created_at=NOW - timedelta(minutes=minutes_ago),
        updated_at=None,
        symbols=[symbol],
        source=source,
        url=None,
        provider=provider,
    )


def test_gs609_on_demand_brief_clusters_corroborating_clinical_news():
    benzinga = [
        article("b1", "Connect Biopharma reports positive Phase 2 COPD topline results", 55),
        article("b2", "Connect Biopharma advances rademikibart toward Phase 3 in COPD", 35, source="NASDAQ"),
    ]
    fmp = [
        article("f1", "Connect Biopharma announces results from global Phase 2 study", 48, source="TipRanks", provider="Financial Modeling Prep"),
        article("noise", "Connect Biopharma schedules investor conference appearance", 20, source="Unknown", provider="Financial Modeling Prep"),
    ]

    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        benzinga_fetcher=lambda _cutoff, _now: benzinga,
        fmp_fetcher=lambda _now: fmp,
    )

    assert report["on_demand_only"] is True
    assert report["autoscan_changed"] is False
    assert report["candidate_membership_changed"] is False
    assert report["trading_authority_changed"] is False
    assert report["cluster_count"] == 1

    cluster = report["clusters"][0]
    assert cluster["symbol"] == "CNTB"
    assert cluster["event_category"] == "REGULATORY_CLINICAL"
    assert cluster["news_class"] == "MATERIAL CATALYST"
    assert cluster["confirmations"] == 3
    assert len(cluster["headlines"]) == 3
    assert "conference appearance" not in str(cluster["headlines"])


def test_gs609_brief_includes_material_risk_events():
    risk = article(
        "risk",
        "Example Corp announces registered direct public offering",
        15,
        symbol="RISK",
        source="Reuters",
    )
    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        benzinga_fetcher=lambda _cutoff, _now: [risk],
        fmp_fetcher=lambda _now: [],
    )

    assert report["cluster_count"] == 1
    cluster = report["clusters"][0]
    assert cluster["symbol"] == "RISK"
    assert cluster["news_class"] == "RISK EVENT"
    assert cluster["event_category"] == "DILUTION_RISK"


def test_gs609_brief_respects_requested_window():
    fresh = article("fresh", "ABCD reports positive Phase 2 trial results", 60, symbol="ABCD")
    stale = article("stale", "OLD reports positive Phase 2 trial results", 300, symbol="OLD")

    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        benzinga_fetcher=lambda _cutoff, _now: [fresh, stale],
        fmp_fetcher=lambda _now: [],
    )

    assert [row["symbol"] for row in report["clusters"]] == ["ABCD"]


def test_gs609_presentation_table_is_compact_and_market_clocked():
    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        benzinga_fetcher=lambda _cutoff, _now: [
            article("b1", "Connect Biopharma reports positive Phase 2 COPD topline results", 30)
        ],
        fmp_fetcher=lambda _now: [],
    )

    rows = presentation_audio.catalyst_brief_table(report)
    assert rows[0]["Ticker"] == "CNTB"
    assert rows[0]["Event"] == "Regulatory / Clinical"
    assert rows[0]["Class"] == "MATERIAL CATALYST"
    assert rows[0]["Confirmations"] == 1
    assert "Phase 2" in rows[0]["Headline"]
    assert rows[0]["Time ET"]


def test_gs609_button_is_fragment_owned_and_does_not_start_scan():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def render_on_demand_catalyst_brief()")
    end = source.index("    render_on_demand_catalyst_brief()", start)
    block = source[start:end]

    assert "@st.fragment" in source[start - 40 : start]
    assert "Run 4-Hour Catalyst Brief" in block
    assert "build_on_demand_catalyst_brief(hours=4)" in block
    assert "request_scan(" not in block
    assert "SCAN_REQUESTED_KEY" not in block
    assert "play_alert(" not in block


def test_gs609_authority_stays_outside_autoscan_discovery_wrappers():
    source = Path("mide/authorities/discovery_news.py").read_text(encoding="utf-8")
    start = source.index("def build_on_demand_catalyst_brief(")
    end = source.index("\ndef build_seed_symbols(*args, **kwargs):", start)
    block = source[start:end]

    assert "discovery.build_seed_symbols =" not in block
    assert "qualified_for_entry" not in block
    assert "mission_rank =" not in block
    assert "request_scan(" not in block
    assert "_BENZINGA_ARTICLE_CACHE" not in block
    assert "_MARKETWIDE_BY_SYMBOL" not in block
