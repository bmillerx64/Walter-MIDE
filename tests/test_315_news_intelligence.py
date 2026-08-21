from datetime import datetime, timedelta, timezone

from mide.gs315_news_intelligence import (
    DIRECT_CATALYST,
    LEGAL_NOISE,
    MORNING_MOVER,
    RECAP,
    STALE,
    WATCHLIST_MENTION,
    classify_news_intelligence,
)
from mide.gs298_news_seeded_discovery import select_material_news_seeds
from mide.news_provider import NewsArticle

UTC = timezone.utc
NOW = datetime(2026, 8, 21, 13, 30, tzinfo=UTC)


def _article(symbol, headline, *, source="Benzinga", age_minutes=15):
    return NewsArticle(
        id=f"{symbol}-{age_minutes}",
        headline=headline,
        created_at=NOW - timedelta(minutes=age_minutes),
        updated_at=None,
        symbols=[symbol],
        source=source,
        url="https://example.test/story",
        provider="Financial Modeling Prep",
    )


def test_direct_material_catalyst_is_high_value_for_discovery_and_catalyst():
    result = classify_news_intelligence(
        "EXYN wins strategic U.S. defense contract",
        source="Reuters",
        age_minutes=12,
        catalyst_score=18,
        trusted_source=True,
    )
    assert result["article_type"] == DIRECT_CATALYST
    assert result["source_quality"] == "TRUSTED"
    assert result["discovery_value"] == "HIGH"
    assert result["catalyst_value"] == "HIGH"


def test_morning_mover_and_watchlist_are_discovery_high_but_catalyst_low():
    mover = classify_news_intelligence(
        "12 Industrials Stocks Moving In Friday's Pre-Market Session",
        source="Benzinga",
        age_minutes=20,
        trusted_source=True,
    )
    watch = classify_news_intelligence(
        "Why These 3 Penny Stocks Are on Investors Radar, 8/21/26",
        source="TipRanks",
        age_minutes=30,
        trusted_source=True,
    )
    assert mover["article_type"] == MORNING_MOVER
    assert mover["discovery_value"] == "HIGH"
    assert mover["catalyst_value"] == "LOW"
    assert watch["article_type"] == WATCHLIST_MENTION
    assert watch["discovery_value"] == "HIGH"
    assert watch["catalyst_value"] == "LOW"


def test_legal_noise_and_recap_do_not_gain_discovery_or_catalyst_weight():
    legal = classify_news_intelligence(
        "Shareholder Alert: Law Firm Reminds Investors of Lead Plaintiff Deadline",
        source="PR Newswire",
        age_minutes=25,
        trusted_source=True,
    )
    recap = classify_news_intelligence(
        "Weekly Report: what happened at ABC last week",
        source="TipRanks",
        age_minutes=40,
        trusted_source=True,
    )
    assert legal["article_type"] == LEGAL_NOISE
    assert legal["discovery_value"] == "LOW"
    assert legal["catalyst_value"] == "NONE"
    assert recap["article_type"] == RECAP
    assert recap["discovery_value"] == "LOW"
    assert recap["catalyst_value"] == "NONE"


def test_stale_news_is_explicitly_classified_stale():
    result = classify_news_intelligence(
        "ABC wins contract",
        source="Reuters",
        age_minutes=361,
        catalyst_score=12,
        trusted_source=True,
    )
    assert result["article_type"] == STALE
    assert result["discovery_value"] == "LOW"
    assert result["catalyst_value"] == "NONE"


def test_existing_news_seed_semantics_are_preserved_while_metadata_is_added():
    selected = select_material_news_seeds(
        [
            _article("XOS", "12 Industrials Stocks Moving In Friday's Pre-Market Session"),
            _article("EXYN", "EXYN wins strategic U.S. defense contract", source="Reuters"),
        ],
        now=NOW,
    )
    by_symbol = {item["symbol"]: item for item in selected}

    assert by_symbol["XOS"]["seed_type"] == "morning_mover_attention"
    assert by_symbol["XOS"]["attention_only"] is True
    assert by_symbol["XOS"]["article_type"] == MORNING_MOVER
    assert by_symbol["XOS"]["catalyst_value"] == "LOW"

    assert by_symbol["EXYN"]["seed_type"] == "material_catalyst"
    assert by_symbol["EXYN"]["attention_only"] is False
    assert by_symbol["EXYN"]["article_type"] == DIRECT_CATALYST
    assert by_symbol["EXYN"]["catalyst_value"] == "HIGH"
