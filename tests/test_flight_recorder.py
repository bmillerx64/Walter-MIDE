from types import SimpleNamespace

from mide.flight_recorder import FlightRecorder, STAGES, prefilter_decision

SETTINGS = SimpleNamespace(
    min_price=0.02, max_price=5.0, min_pct_change=5.0, min_day_volume=100_000
)


def snapshot(price=1.0, volume=200_000, previous_close=0.9):
    return {
        "latestTrade": {"p": price},
        "latestQuote": {"bp": price - 0.01, "ap": price + 0.01},
        "dailyBar": {"c": price, "v": volume},
        "prevDailyBar": {"c": previous_close},
    }


def test_prefilter_decision_exposes_exact_measurements_and_thresholds():
    decision = prefilter_decision(
        "LOW", snapshot(volume=10, previous_close=1.0), SETTINGS
    )

    assert decision["passed"] is False
    assert "pct_change 0 < 5" in decision["reason"]
    assert decision["measured_values"]["volume"] == 10
    assert decision["thresholds"]["min_day_volume"] == 100_000


def test_recorder_persists_complete_paths_funnel_and_latest_lookup(tmp_path):
    recorder = FlightRecorder(tmp_path / "flights.jsonl")
    gate = {
        "passed": True,
        "reason": "Participation Present",
        "checks": [{"condition": "pace", "measured": 1.4, "threshold": 1.2}],
    }
    structure = {
        "passed": True,
        "reason": "Structure Ready",
        "checks": [
            {"condition": "Near VWAP", "measured": 0.5, "threshold": "-1.0 to 2.5%"}
        ],
    }
    record = {
        "symbol": "PASS",
        "status": "Strengthening",
        "qualified_for_ranking": True,
        "participation_gate": gate,
        "structure_gate": structure,
    }
    scan = recorder.record_scan(
        seeds=["PASS", "DROP"],
        discovery_reasons={"PASS": ["market mover"], "DROP": ["recent news"]},
        snapshots={"PASS": snapshot(), "DROP": snapshot(price=8)},
        candidates=[{"symbol": "PASS"}],
        analyzed=[record],
        records=[record],
        settings=SETTINGS,
        scanner_v2=True,
    )

    assert scan["funnel"] == {
        "Sampled": 2,
        "Prefiltered": 1,
        "Analyzed": 1,
        "Participation PASS": 1,
        "Structure PASS": 1,
        "Qualified": 1,
        "Displayed": 1,
    }
    trace = recorder.latest_for_symbol("drop")
    assert [event["stage"] for event in trace["events"]] == list(STAGES)
    assert trace["events"][2]["passed"] is False
    assert "outside" in trace["events"][2]["reason"]
    assert recorder.latest_for_symbol("missing") is None
