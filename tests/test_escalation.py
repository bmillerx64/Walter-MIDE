from mide.escalation import (
    ENTRY_WINDOW_OPEN,
    MONITOR,
    TOO_EXTENDED,
    WATCH_CLOSELY,
    confidence_trend,
    escalation_alert_phrase,
    escalation_state,
    meaningful_evidence_deltas,
    ready_checklist,
)


def record(**overrides):
    value = {
        "symbol": "WALT",
        "candidate_status": "Watching",
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "conviction_score": 72,
        "participation_score": 82,
        "volume_acceleration": 1.4,
    }
    value.update(overrides)
    return value


def test_escalation_states_translate_completed_scanner_decisions():
    assert escalation_state(record(qualified_for_entry=True)) == ENTRY_WINDOW_OPEN
    assert escalation_state(record(candidate_status="Strengthening")) == WATCH_CLOSELY
    assert escalation_state(record(candidate_status="Emerging")) == MONITOR
    assert (
        escalation_state(record(qualified_for_entry=True, vwap_distance_pct=5.1))
        == TOO_EXTENDED
    )


def test_ready_checklist_uses_existing_gate_and_trigger_results():
    checks = ready_checklist(
        record(
            participation_gate={"passed": True},
            structure_gate={"passed": False},
            trigger_diagnostics={"passed": True},
        )
    )
    assert [(item["label"], item["ready"]) for item in checks] == [
        ("Participation qualified", True),
        ("Structure qualified", False),
        ("Holding above VWAP", True),
        ("Trend confirmation", True),
        ("Entry trigger", True),
    ]


def test_confidence_trend_and_deltas_compare_immediately_prior_scan():
    current = record(
        conviction_score=78,
        participation_score=89,
        vwap_distance_pct=0.5,
        volume_acceleration=1.45,
        opportunity_pulse_previous={
            "conviction_score": 72,
            "participation_score": 84,
            "vwap_distance_pct": 1.0,
            "volume_acceleration": 1.4,
        },
    )
    assert confidence_trend(current) == {
        "direction": "Rising",
        "delta": 6.0,
        "current": 78.0,
    }
    assert [
        (item["label"], item["direction"])
        for item in meaningful_evidence_deltas(current)
    ] == [
        ("Confidence", "improved"),
        ("Participation", "improved"),
        ("VWAP distance", "improved"),
    ]


def test_alert_only_announces_a_real_escalation_state_change():
    changed = record(
        candidate_status="Strengthening",
        opportunity_pulse_previous=record(candidate_status="Watching"),
    )
    unchanged = record(opportunity_pulse_previous=record())
    assert (
        escalation_alert_phrase([changed])
        == "WALT escalation changed to Watch Closely."
    )
    assert escalation_alert_phrase([unchanged]) == ""


def test_engine_does_not_mutate_scanner_record():
    source = record(opportunity_pulse_previous=record(conviction_score=70))
    before = repr(source)
    escalation_state(source)
    confidence_trend(source)
    ready_checklist(source)
    meaningful_evidence_deltas(source)
    assert repr(source) == before
