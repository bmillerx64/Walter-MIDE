from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs480_catalyst_story_intelligence as gs480
from mide.news_provider import FMPNewsProvider


UTC = timezone.utc
NOW = datetime(2026, 9, 17, 15, 4, tzinfo=UTC)


def paai_row():
    return {
        "symbol": "RTB",
        "publishedDate": "2026-09-17T15:00:00Z",
        "publisher": "GlobeNewswire",
        "title": "Roundtable Secures 10-Year, $1 Billion Agreement, Bringing its AI/DeFi Media Operating System to Global Scale and Profitability",
        "text": (
            "Roundtable announced a 10-year, $1 billion agreement with The Arena Group, "
            "now Paradium.AI (NYSE: PAAI). The parties forecast a $100 million annualized "
            "revenue run rate and EBITDA-positive operations, subject to a minority "
            "investment of $89 million cash and stock for approximately 49% ownership. "
            "The platform is expected to reach 100 million consumers."
        ),
        "url": "https://example.test/paai",
    }


def test_explicit_cross_ticker_from_story_is_added_without_guessing_capital_words():
    assert gs480.explicit_ticker_mentions(
        "Paradium.AI (NYSE: PAAI) works with RTB and AI teams"
    ) == ["PAAI"]
    assert gs480.explicit_ticker_mentions(
        "Company discusses AI, EBITDA, CEO and RTB without a ticker label"
    ) == []


def test_paai_story_catalogs_event_semantics_and_number_roles_without_trade_authority():
    row = paai_row()
    detail = gs480.story_intelligence(row["title"], row["text"])

    assert "CONTRACT_ORDER" in detail["categories"]
    assert "M_AND_A_INVESTMENT" in detail["categories"]
    assert "FINANCIAL_GROWTH" in detail["categories"]
    assert detail["material_attention"] is True
    roles = {item["role"] for item in detail["quantities"]}
    assert "DEAL_OR_BACKLOG" in roles
    assert "REVENUE" in roles
    assert "INVESTMENT_OR_FUNDING" in roles
    assert detail["catalyst_score_changed"] is False
    assert detail["trading_authority_changed"] is False


def test_raw_growth_and_large_count_do_not_become_material_catalyst_by_themselves():
    detail = gs480.story_intelligence(
        "Company discusses long-term growth",
        "The addressable audience includes 500,000 consumers.",
    )

    assert detail["material_attention"] is False
    assert detail["positive_attention_categories"] == []
    assert any(item["normalized_value"] == 500_000 for item in detail["quantities"])
    assert detail["generic_growth_word_alone_is_material"] is False


def test_dilution_language_is_cataloged_as_risk_not_growth_attention():
    detail = gs480.story_intelligence(
        "Company announces $20 million registered direct offering",
        "Gross proceeds are expected to be $20 million before expenses.",
    )

    assert "DILUTION_RISK" in detail["risk_categories"]
    assert detail["material_attention"] is False
    assert any(item["role"] == "DILUTION_OR_FINANCING" for item in detail["quantities"])


def test_fmp_normalization_retains_bounded_story_and_explicit_paai_symbol():
    gs480._install_article_transport()
    article = FMPNewsProvider._normalize(paai_row(), endpoint="news/stock")

    assert article is not None
    assert set(article.symbols) == {"RTB", "PAAI"}
    assert getattr(article, "_walter_explicit_symbols") == ["PAAI"]
    assert "100 million annualized revenue" in getattr(article, "_walter_story_text")
    serialized = article.as_dict()
    assert serialized["text"].startswith("Roundtable announced")
    assert serialized["explicit_symbols"] == ["PAAI"]
    assert "CONTRACT_ORDER" in serialized["story_context"]["categories"]


def test_trusted_story_body_can_create_attention_identity_without_catalyst_score_boost(monkeypatch):
    from mide import gs298_news_seeded_discovery as gs298

    gs480._install_article_transport()
    baseline = gs298.select_material_news_seeds
    gs480._install_marketwide_selection()

    row = paai_row()
    row["title"] = "Roundtable announces corporate update"
    article = FMPNewsProvider._normalize(row, endpoint="news/stock")
    selected = gs298.select_material_news_seeds([article], now=lambda: NOW, limit=20)
    paai = next(item for item in selected if item["symbol"] == "PAAI")

    assert paai["seed_type"] == gs480.STORY_SEED_TYPE
    assert paai["attention_only"] is True
    assert paai["story_derived"] is True
    assert paai["catalyst_score"] == 0.0
    assert "CONTRACT_ORDER" in paai["story_context"]["categories"]
    # Keep the reference live so the test documents that GS480 wraps rather than
    # replaces the established GS298/315 selector contract.
    assert callable(baseline)


def test_recorder_wrapper_persists_news_clock_for_symbol_without_ranked_record(monkeypatch):
    captured = {}

    def baseline(_self, scan, records):
        captured["scan"] = scan
        captured["records"] = records
        return scan

    monkeypatch.setattr(gs480, "_LATEST_MARKETWIDE_TRACE", [{
        "symbol": "PAAI", "headline": "10-year $1B agreement",
        "created_at": "2026-09-17T15:00:00+00:00", "identity_added": False,
    }])
    monkeypatch.setattr(gs480, "_LATEST_TARGETED_TRACE", {
        "PAAI": {
            "symbol": "PAAI", "article_found": True,
            "headline": "10-year $1B agreement",
            "created_at": "2026-09-17T15:00:00+00:00",
            "age_seconds_at_scan": 240.0,
            "source": "GlobeNewswire", "provider": "Financial Modeling Prep",
            "catalyst_score": 8, "explicit_symbols": ["PAAI"],
            "story_context": {"categories": ["CONTRACT_ORDER"]},
            "marketwide_handoff": True,
        }
    })
    wrapped = gs480._recorder_wrapper(baseline)
    scan = {"symbols": [{"symbol": "PAAI", "evidence": {}}]}

    wrapped(object(), scan, [])

    evidence = captured["scan"]["symbols"][0]["evidence"]
    assert evidence["news_headline"] == "10-year $1B agreement"
    assert evidence["news_age_seconds_at_scan"] == 240.0
    assert evidence["news_marketwide_handoff"] is True
    assert evidence["catalyst_story"]["categories"] == ["CONTRACT_ORDER"]
    assert captured["scan"]["news_trace"]["marketwide_selected"][0]["symbol"] == "PAAI"
    assert captured["scan"]["news_trace"]["additional_provider_requests"] == 0


def test_story_cache_freshness_is_bounded():
    gs480._MARKETWIDE_BY_SYMBOL.clear()

    class Article:
        headline = "Contract award"
        source = "Reuters"
        provider = "Financial Modeling Prep"
        symbols = ["OLD"]
        created_at = datetime.now(UTC) - timedelta(hours=7)

    gs480._remember_marketwide([Article()])
    assert "OLD" not in gs480._MARKETWIDE_BY_SYMBOL


def test_startup_binds_gs480_after_recorder_hard_bind():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs480_catalyst_story_intelligence" in source
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs427()") < body.index("install_gs480()") < body.index("install_gs428()")


def test_gs480_scope_lock_keeps_news_out_of_trading_authority():
    source = Path("mide/gs480_catalyst_story_intelligence.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "opportunity_score =",
        "conviction_score =",
        "execute_order",
        "place_order",
        "client.bars(",
        "client.snapshots(",
        "client.latest_trades(",
    )
    for token in forbidden:
        assert token not in source
