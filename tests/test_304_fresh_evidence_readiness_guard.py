from copy import deepcopy
from datetime import datetime, timedelta, timezone

from mide.gs304_fresh_evidence_readiness_guard import evidence_guarded_readiness


def _record(*, age_seconds=30, include_timeframes=True):
    now = datetime.now(timezone.utc)
    record = {
        "symbol": "ARCT",
        "price": 10.35,
        "volume": 5_630_164,
        "vwap_value": 10.1,
        "supertrend_bullish": True,
        "source_bar_timestamp": (now - timedelta(seconds=age_seconds)).isoformat(),
        "source_bar_age": age_seconds,
    }
    if include_timeframes:
        record["timeframe_alignment"] = {"1m": True, "3m": True}
    return record


def _item(record):
    return {"record": record, "confidence": 85, "conditions": []}


def test_stale_entry_window_is_capped_to_watch():
    item = _item(_record(age_seconds=600))
    guarded = evidence_guarded_readiness(
        item,
        {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."},
    )
    assert guarded == {
        "index": 1,
        "state": "WATCH",
        "sentence": "Market evidence is stale. Refresh before entry.",
    }


def test_trusted_entry_window_remains_entry_window():
    item = _item(_record(age_seconds=30))
    base = {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."}
    assert evidence_guarded_readiness(item, base) == base


def test_nontrusted_building_state_is_not_demoted():
    item = _item(_record(age_seconds=600))
    base = {"index": 2, "state": "BUILDING", "sentence": "Momentum building."}
    assert evidence_guarded_readiness(item, base) == base


def test_incomplete_ready_state_is_capped():
    record = _record(age_seconds=30, include_timeframes=False)
    item = _item(record)
    guarded = evidence_guarded_readiness(
        item,
        {"index": 3, "state": "READY", "sentence": "Momentum confirmed."},
    )
    assert guarded["state"] == "WATCH"
    assert "incomplete" in guarded["sentence"].lower()


def test_unknown_freshness_preserves_legacy_presentation_contract():
    record = {
        "symbol": "LEGACY",
        "price": 1.0,
        "volume": 1_000_000,
        "vwap_value": 0.98,
        "supertrend_bullish": True,
    }
    base = {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."}
    assert evidence_guarded_readiness(_item(record), base) == base


def test_guard_does_not_mutate_candidate_or_base_result():
    record = _record(age_seconds=600)
    item = _item(record)
    base = {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."}
    before_item = deepcopy(item)
    before_base = deepcopy(base)
    evidence_guarded_readiness(item, base)
    assert item == before_item
    assert base == before_base
