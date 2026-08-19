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
    assert guarded["state"] == "WATCH"
    assert guarded["index"] == 1
    assert guarded["evidence_status"] == "CAUTION"
    assert guarded["evidence_guarded"] is True
    assert "stale" in guarded["sentence"].lower()


def test_trusted_entry_window_remains_entry_window():
    item = _item(_record(age_seconds=30))
    guarded = evidence_guarded_readiness(
        item,
        {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."},
    )
    assert guarded["state"] == "ENTRY WINDOW"
    assert guarded["index"] == 4
    assert guarded["evidence_status"] == "TRUSTED"
    assert guarded["evidence_guarded"] is False


def test_nontrusted_building_state_is_not_demoted():
    item = _item(_record(age_seconds=600))
    guarded = evidence_guarded_readiness(
        item,
        {"index": 2, "state": "BUILDING", "sentence": "Momentum building."},
    )
    assert guarded["state"] == "BUILDING"
    assert guarded["index"] == 2
    assert guarded["evidence_guarded"] is False


def test_incomplete_ready_state_is_capped():
    record = _record(age_seconds=30, include_timeframes=False)
    item = _item(record)
    guarded = evidence_guarded_readiness(
        item,
        {"index": 3, "state": "READY", "sentence": "Momentum confirmed."},
    )
    assert guarded["state"] == "WATCH"
    assert guarded["evidence_status"] == "CAUTION"
    assert "incomplete" in guarded["sentence"].lower()


def test_guard_does_not_mutate_candidate_or_base_result():
    record = _record(age_seconds=600)
    item = _item(record)
    base = {"index": 4, "state": "ENTRY WINDOW", "sentence": "Entry conditions aligned."}
    before_item = deepcopy(item)
    before_base = deepcopy(base)
    evidence_guarded_readiness(item, base)
    assert item == before_item
    assert base == before_base
