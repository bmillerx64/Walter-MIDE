from copy import deepcopy
from types import SimpleNamespace

from mide import ui
from mide.flight_recorder import FlightRecorder
from mide.gs310_unified_opportunity_state import DEVELOPING, opportunity_state
from mide.gs414_final_enriched_opportunity_order import final_enriched_opportunity_records
from mide.gs415_qualified_pass_visibility import (
    default_actionable_display_records,
    legacy_status_visible,
)


SETTINGS = SimpleNamespace(
    min_price=0.02,
    max_price=5.0,
    min_pct_change=5.0,
    min_day_volume=100_000,
    max_free_float=3_500_000,
)


def _qualified_pass_record() -> dict:
    return {
        "symbol": "QPASS",
        "status": "PASS",
        "candidate_status": "Watching",
        "qualified_for_ranking": True,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "price": 1.008,
        "vwap_value": 1.0,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_score": 40.0,
        "participation_surge_score": 40.0,
        "expansion_quality": 45.0,
        "volume_acceleration": 0.9,
        "source_bar_age_seconds": 30.0,
        "discovery_reasons": [],
        "reasons": [],
        "cautions": [],
    }


def _snapshot() -> dict:
    return {
        "latestTrade": {"p": 1.008},
        "latestQuote": {"bp": 1.00, "ap": 1.01},
        "dailyBar": {"c": 1.008, "v": 250_000},
        "prevDailyBar": {"c": 0.90},
        "free_float": 1_000_000,
    }


def test_qualified_ranked_pass_reaches_existing_opportunity_interpreter_without_authority():
    record = _qualified_pass_record()
    before = deepcopy(record)

    actionable = ui.actionable_candidate_records([record])
    assert actionable == [record]
    assert default_actionable_display_records(actionable) == [record]

    ordered = final_enriched_opportunity_records([record])
    assert [item["symbol"] for item in ordered] == ["QPASS"]
    view = opportunity_state(ordered[0])

    assert view["state"] == DEVELOPING
    assert record == before
    assert record["status"] == "PASS"
    assert record["qualified_for_entry"] is False
    assert record["qualified_for_alert"] is False


def test_gs415_removes_only_pass_from_the_legacy_display_veto():
    qualified_pass = _qualified_pass_record()
    removed = {**qualified_pass, "symbol": "GONE", "status": "Removed"}

    assert legacy_status_visible(qualified_pass) is True
    assert legacy_status_visible(removed) is False
    assert default_actionable_display_records([qualified_pass, removed]) == [qualified_pass]


def test_flight_recorder_no_longer_reports_qualified_pass_as_hidden(tmp_path):
    recorder = FlightRecorder(tmp_path / "flights.jsonl")
    record = _qualified_pass_record()
    record["participation_gate"] = {
        "passed": True,
        "reason": "Participation Present",
        "checks": [],
    }
    record["structure_gate"] = {
        "passed": True,
        "reason": "Structure Ready",
        "checks": [],
    }

    scan = recorder.record_scan(
        seeds=["QPASS"],
        discovery_reasons={"QPASS": ["market mover"]},
        snapshots={"QPASS": _snapshot()},
        candidates=[{"symbol": "QPASS"}],
        analyzed=[record],
        records=[record],
        settings=SETTINGS,
        scanner_v2=True,
    )

    trace = scan["symbols"][0]
    display_event = next(
        event for event in trace["events"] if event["stage"] == "actionable display"
    )

    assert scan["funnel"]["Qualified"] == 1
    assert scan["funnel"]["Displayed"] == 1
    assert display_event["passed"] is True
    assert display_event["reason"] == "shown in actionable display"
    assert display_event["thresholds"]["hidden_statuses"] == ["Removed"]
    assert record["status"] == "PASS"
    assert record["qualified_for_entry"] is False
    assert record["qualified_for_alert"] is False
