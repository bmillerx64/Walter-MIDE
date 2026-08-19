from mide.escalation import (
    ENTRY_WINDOW_OPEN,
    MONITOR,
    TOO_EXTENDED,
    WATCH_CLOSELY,
    confidence_trend,
    escalation_alert_phrase,
    escalation_state,
    meaningful_evidence_deltas,
    momentum_urgency,
    ready_checklist,
    trade_recommendation,
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


def test_fresh_multi_signal_improvement_promotes_review_urgency():
    current = record(
        candidate_status="Watching",
        conviction_score=63,
        participation_score=78,
        vwap_distance_pct=0.7,
        volume_acceleration=1.45,
        rvol=2.2,
        opportunity_pulse_previous={
            "candidate_status": "Watching",
            "conviction_score": 56,
            "participation_score": 70,
            "vwap_relation": "above",
            "vwap_distance_pct": 1.2,
            "supertrend_bullish": True,
            "volume_acceleration": 1.15,
            "rvol": 1.6,
        },
    )
    urgency = momentum_urgency(current)
    assert urgency["promoted"] is True
    assert urgency["continuity"] is True
    assert urgency["vwap_supported"] is True
    assert urgency["trend_supported"] is True
    assert "Confidence" in urgency["improving_signals"]
    assert "Participation" in urgency["improving_signals"]
    assert escalation_state(current) == WATCH_CLOSELY


def test_single_scan_or_unconfirmed_structure_does_not_manufacture_urgency():
    assert momentum_urgency(record(conviction_score=90))["promoted"] is False
    current = record(
        conviction_score=78,
        participation_score=90,
        vwap_relation="below",
        opportunity_pulse_previous={
            "conviction_score": 70,
            "participation_score": 82,
            "vwap_relation": "below",
            "vwap_distance_pct": 0.9,
            "supertrend_bullish": True,
        },
    )
    assert momentum_urgency(current)["promoted"] is False
    assert escalation_state(current) == MONITOR


def test_overextension_remains_hard_stop_even_when_momentum_improves():
    current = record(
        conviction_score=82,
        participation_score=92,
        vwap_distance_pct=5.5,
        volume_acceleration=1.8,
        opportunity_pulse_previous={
            "conviction_score": 70,
            "participation_score": 82,
            "vwap_relation": "above",
            "vwap_distance_pct": 4.5,
            "supertrend_bullish": True,
            "volume_acceleration": 1.4,
        },
    )
    assert escalation_state(current) == TOO_EXTENDED


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
    momentum_urgency(source)
    assert repr(source) == before


def test_recommendation_is_green_when_every_requirement_aligns():
    result = trade_recommendation(
        record(qualified_for_entry=True, trigger_diagnostics={"passed": True})
    )
    assert result["label"] == "GREEN LIGHT"
    assert result["remaining"] == 0
    assert "next candle" in result["message"]


def test_recommendation_gets_ready_only_when_one_condition_remains():
    result = trade_recommendation(
        record(qualified_for_entry=False, trigger_diagnostics={"passed": False})
    )
    assert result == {
        "label": "GET READY",
        "emoji": "🟡",
        "message": "One condition remains: Entry trigger.",
        "remaining": 1,
    }


def test_recommendation_rejects_multiple_blockers_or_extended_price():
    blocked = trade_recommendation(
        record(vwap_relation="below", supertrend_bullish=False)
    )
    extended = trade_recommendation(
        record(
            qualified_for_entry=True,
            trigger_diagnostics={"passed": True},
            vwap_distance_pct=5.1,
        )
    )
    assert blocked["label"] == "NO TRADE"
    assert extended["label"] == "NO TRADE"
