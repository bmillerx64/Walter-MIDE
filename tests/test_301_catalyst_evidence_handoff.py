from datetime import datetime, timedelta, timezone

from mide.gs301_catalyst_evidence_handoff import (
    catalyst_handoff_articles,
    merge_catalyst_handoff,
)
from mide.news import index_news

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)


def watch_item(symbol="AZI", *, source="Reuters", headline=None, age_hours=2):
    published = NOW - timedelta(hours=age_hours)
    return {
        "symbol": symbol,
        "source": source,
        "headline": headline or f"{symbol} receives strategic investment",
        "catalyst_score": 9,
        "catalyst_flags": ["capital_injection"],
        "trusted_source": source in {"Reuters", "Benzinga"},
        "published_at": published.isoformat(),
        "expires_at": (published + timedelta(hours=6)).isoformat(),
    }


def test_requested_fresh_reuters_watch_rehydrates_into_catalyst_article():
    articles = catalyst_handoff_articles(
        {"AZI": watch_item()}, requested_symbols=["AZI"], now=NOW
    )
    assert len(articles) == 1
    assert articles[0]["symbols"] == ["AZI"]
    assert articles[0]["source"] == "Reuters"
    assert articles[0]["provider"] == "Financial Modeling Prep"
    assert articles[0]["gs301_handoff"] is True
    indexed = index_news(articles)
    assert indexed["AZI"]["catalyst_score"] >= 7
    assert "source_quality:trusted" in indexed["AZI"]["flags"]


def test_benzinga_source_label_is_preserved_exactly():
    articles = catalyst_handoff_articles(
        {"BENZ": watch_item("BENZ", source="Benzinga")},
        requested_symbols=["BENZ"],
        now=NOW,
    )
    assert articles[0]["source"] == "Benzinga"
    assert "source_quality:trusted" in index_news(articles)["BENZ"]["flags"]


def test_unrequested_or_expired_watch_cannot_enter_catalyst_results():
    expired = watch_item("OLD", age_hours=7)
    assert catalyst_handoff_articles(
        {"AZI": watch_item(), "OLD": expired},
        requested_symbols=["OTHER", "OLD"],
        now=NOW,
    ) == []


def test_watch_is_reclassified_and_neutral_or_negative_state_is_not_trusted():
    neutral = watch_item("NEUT", headline="NEUT announces corporate update")
    negative = watch_item("DILUTE", headline="DILUTE announces registered direct offering")
    assert catalyst_handoff_articles(
        {"NEUT": neutral, "DILUTE": negative},
        requested_symbols=["NEUT", "DILUTE"],
        now=NOW,
    ) == []


def test_provider_returned_same_article_is_not_duplicated_by_handoff():
    handoff = catalyst_handoff_articles(
        {"AZI": watch_item()}, requested_symbols=["AZI"], now=NOW
    )
    provider_copy = dict(handoff[0])
    provider_copy.pop("gs301_handoff")
    provider_copy.pop("gs301_catalyst_score")
    provider_copy.pop("gs301_catalyst_flags")
    merged, added = merge_catalyst_handoff([provider_copy], handoff)
    assert len(merged) == 1
    assert added == []


def test_newer_negative_provider_story_can_supersede_handoff_material_positive():
    handoff = catalyst_handoff_articles(
        {"AZI": watch_item()}, requested_symbols=["AZI"], now=NOW
    )
    newer_negative = {
        "id": "provider-negative",
        "headline": "AZI announces registered direct offering",
        "created_at": (NOW - timedelta(minutes=15)).isoformat(),
        "updated_at": None,
        "symbols": ["AZI"],
        "source": "Reuters",
        "url": None,
        "provider": "Financial Modeling Prep",
    }
    merged, added = merge_catalyst_handoff([newer_negative], handoff)
    assert added == ["AZI"]
    selected = index_news(merged)["AZI"]
    assert selected["headline"] == newer_negative["headline"]
    assert selected["catalyst_score"] < 0


def test_handoff_merge_does_not_mutate_provider_results():
    fetched = [{
        "id": "x",
        "headline": "OTHER announces agreement",
        "created_at": NOW.isoformat(),
        "updated_at": None,
        "symbols": ["OTHER"],
        "source": "Reuters",
        "url": None,
        "provider": "Financial Modeling Prep",
    }]
    before = repr(fetched)
    handoff = catalyst_handoff_articles(
        {"AZI": watch_item()}, requested_symbols=["AZI"], now=NOW
    )
    merge_catalyst_handoff(fetched, handoff)
    assert repr(fetched) == before
