from datetime import datetime, timedelta, timezone

from mide.gs299_news_reaction_watch import (
    REACTION_WATCH_REASON,
    merge_reaction_watch,
    update_reaction_watch,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)


def evidence(symbol="AZI", *, age_minutes=60, source="Reuters"):
    return {
        "symbol": symbol,
        "source": source,
        "headline": f"{symbol} receives strategic investment",
        "age_minutes": age_minutes,
        "catalyst_score": 9,
        "catalyst_flags": ["capital_injection"],
        "trusted_source": source in {"Reuters", "Benzinga"},
    }


def test_current_news_seed_becomes_watch_with_original_six_hour_expiry():
    watch = update_reaction_watch({}, [evidence(age_minutes=90)], now=NOW)
    item = watch["AZI"]
    assert item["source"] == "Reuters"
    assert item["published_at"] == (NOW - timedelta(minutes=90)).isoformat()
    assert item["expires_at"] == (NOW + timedelta(hours=4, minutes=30)).isoformat()


def test_reuters_and_benzinga_provenance_survive_watch_retention():
    watch = update_reaction_watch(
        {},
        [evidence("RTR", source="Reuters"), evidence("BENZ", source="Benzinga")],
        now=NOW,
    )
    assert watch["RTR"]["source"] == "Reuters"
    assert watch["BENZ"]["source"] == "Benzinga"
    assert watch["RTR"]["trusted_source"] is True
    assert watch["BENZ"]["trusted_source"] is True


def test_prior_watch_survives_feed_page_churn_until_original_expiry():
    prior = {
        "AZI": {
            "symbol": "AZI",
            "source": "Reuters",
            "headline": "AZI receives strategic investment",
            "published_at": (NOW - timedelta(hours=2)).isoformat(),
            "expires_at": (NOW + timedelta(hours=4)).isoformat(),
        }
    }
    watch = update_reaction_watch(prior, [], now=NOW)
    assert "AZI" in watch


def test_expired_watch_is_removed_and_cannot_be_reseeded_by_stale_evidence():
    prior = {
        "OLD": {
            "symbol": "OLD",
            "source": "Reuters",
            "published_at": (NOW - timedelta(hours=7)).isoformat(),
            "expires_at": (NOW - timedelta(hours=1)).isoformat(),
        }
    }
    watch = update_reaction_watch(prior, [evidence("STALE", age_minutes=361)], now=NOW)
    assert watch == {}


def test_watch_merges_identity_only_without_duplicating_native_or_gs298_symbols():
    watch = update_reaction_watch(
        {}, [evidence("AZI"), evidence("SKK", age_minutes=30)], now=NOW
    )
    seeds, reasons, added = merge_reaction_watch(
        ["AZI", "NATIVE"], {"AZI": ["FMP material news seed: Reuters"]}, watch
    )
    assert seeds == ["AZI", "NATIVE", "SKK"]
    assert [item["symbol"] for item in added] == ["SKK"]
    assert reasons["SKK"] == [f"{REACTION_WATCH_REASON}: Reuters"]
    assert "headline" not in reasons["SKK"][0].lower()


def test_watch_merge_is_bounded_and_newest_catalysts_get_priority():
    current = [
        evidence("OLD", age_minutes=120),
        evidence("NEW", age_minutes=10),
        evidence("MID", age_minutes=60),
    ]
    watch = update_reaction_watch({}, current, now=NOW)
    seeds, _reasons, added = merge_reaction_watch([], {}, watch, limit=2)
    assert seeds == ["NEW", "MID"]
    assert [item["symbol"] for item in added] == ["NEW", "MID"]


def test_refreshing_same_article_does_not_extend_beyond_publication_plus_six_hours():
    first = update_reaction_watch({}, [evidence(age_minutes=60)], now=NOW)
    later = NOW + timedelta(hours=2)
    # Same article is now three hours old. Its expiry remains publication + 6h.
    refreshed = update_reaction_watch(first, [evidence(age_minutes=180)], now=later)
    assert refreshed["AZI"]["published_at"] == (NOW - timedelta(hours=1)).isoformat()
    assert refreshed["AZI"]["expires_at"] == (NOW + timedelta(hours=5)).isoformat()
