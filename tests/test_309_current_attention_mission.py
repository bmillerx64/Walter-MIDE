from mide.gs309_current_attention_mission import (
    ABSOLUTE_VOLUME_REASON,
    DAY_GAINERS_REASON,
    RELATIVE_VOLUME_REASON,
    annotate_native_attention_reasons,
    current_attention_provenance,
    current_attention_records,
    mission_attention_eligible,
)


class FakeClient:
    _native_radar_prices = {
        "HOT": {"sources": ["day_gainers", "absolute_volume"]},
        "BUSY": {"sources": ["absolute_volume", "relative_volume"]},
    }


def test_native_feed_provenance_is_added_without_changing_membership():
    seeds = ["HOT", "BUSY", "NEWS"]
    reasons = {"NEWS": ["FMP morning mover attention seed: Benzinga"]}

    annotated = annotate_native_attention_reasons(FakeClient(), seeds, reasons)

    assert seeds == ["HOT", "BUSY", "NEWS"]
    assert DAY_GAINERS_REASON in annotated["HOT"]
    assert ABSOLUTE_VOLUME_REASON in annotated["HOT"]
    assert ABSOLUTE_VOLUME_REASON in annotated["BUSY"]
    assert RELATIVE_VOLUME_REASON in annotated["BUSY"]
    assert annotated["NEWS"] == ["FMP morning mover attention seed: Benzinga"]


def test_current_day_gainer_is_mission_eligible():
    record = {"symbol": "HOT", "discovery_reasons": [DAY_GAINERS_REASON]}

    assert mission_attention_eligible(record)
    assert current_attention_provenance(record) == ("WEBULL_TOP_MOVER",)


def test_absolute_or_relative_volume_alone_does_not_hold_mission_slot():
    record = {
        "symbol": "BUSY",
        "discovery_reasons": [ABSOLUTE_VOLUME_REASON, RELATIVE_VOLUME_REASON],
    }

    assert not mission_attention_eligible(record)
    assert current_attention_provenance(record) == ()


def test_fresh_morning_news_seed_can_reach_mission_before_top_gainers():
    record = {
        "symbol": "EARLY",
        "discovery_reasons": ["FMP morning mover attention seed: Benzinga"],
    }

    assert mission_attention_eligible(record)
    assert current_attention_provenance(record) == ("FRESH_NEWS_SEED",)


def test_material_news_seed_can_reach_mission_before_top_gainers():
    record = {
        "symbol": "CAT",
        "discovery_reasons": ["FMP material news seed: Reuters"],
    }

    assert mission_attention_eligible(record)
    assert current_attention_provenance(record) == ("FRESH_NEWS_SEED",)


def test_filter_preserves_source_records_and_order():
    stale = {"symbol": "OLD", "discovery_reasons": [ABSOLUTE_VOLUME_REASON]}
    hot = {"symbol": "HOT", "discovery_reasons": [DAY_GAINERS_REASON]}
    news = {"symbol": "NEWS", "discovery_reasons": ["FMP morning mover attention seed: Benzinga"]}
    records = [stale, hot, news]

    selected = current_attention_records(records)

    assert selected == [hot, news]
    assert records == [stale, hot, news]
