from mide import gs473_operator_attention_audio as gs473
from mide import gs492_maturation_transition_audio as gs492
from mide import gs512_audio_architecture_gate_bridge as gs512
from mide.gs365_chime_semantic_classifier import semantic_chime_count


def _tf():
    return {
        "data_available": True,
        "current_supertrend_bullish": True,
        "current_above_vwap": True,
    }


def _lobo():
    return {
        "symbol": "LOBO",
        "status": "WATCH NOW",
        "candidate_status": "Removed",
        "price": 0.7307,
        "pct_change": 37.8679,
        "vwap_distance_pct": 0.7227,
        "supertrend_bullish": True,
        "participation_score": 63.2,
        "expansion_quality": 54.5,
        "mission_rank": 3,
        "architecture_audit": [
            {
                "stage": "Participation Assessment",
                "decision": "Qualified",
                "reason": "Participation evidence measured",
            },
            {
                "stage": "Expansion Assessment",
                "decision": "Qualified",
                "reason": "Confluence 82",
            },
        ],
        "timeframes": {
            "30s": _tf(),
            "1m": _tf(),
            "3m": _tf(),
            "5m": _tf(),
            "10m": _tf(),
        },
    }


def test_lobo_architecture_qualified_watch_now_is_audible_without_legacy_gates():
    gs512.install()
    record = _lobo()

    assert "participation_gate" not in record
    assert "structure_gate" not in record
    detail = gs473.operator_attention_candidate(record)
    assert detail["active"] is True
    assert detail["fresh"] is True

    phrase = gs473.operator_attention_audio_phrase([record])
    assert phrase.startswith("LOBO. LOOK NOW.")
    assert semantic_chime_count(phrase) == 2


def test_maturation_audio_uses_same_architecture_gate_truth():
    gs512.install()
    record = _lobo()
    record["timeframes"]["1m"]["st_vwap_line_cross"] = {"new": True}

    detail = gs492.maturation_transition(record)
    assert detail["gates_passed"] is True
    assert detail["stage"] == "RUNNER_DETECTED"


def test_explicit_failed_gate_overrides_architecture_compatibility():
    gs512.install()
    record = _lobo()
    record["participation_gate"] = {"passed": False}

    assert gs512.authoritative_gate_passed(record, "participation_gate") is False
    assert gs473.operator_attention_candidate(record)["active"] is False


def test_rejected_architecture_stage_does_not_manufacture_audio():
    gs512.install()
    record = _lobo()
    for row in record["architecture_audit"]:
        if row["stage"] == "Participation Assessment":
            row["decision"] = "Rejected"
            row["reason"] = "Participation evidence insufficient"

    assert gs512.authoritative_gate_passed(record, "participation_gate") is False
    assert gs473.operator_attention_audio_phrase([record]) == ""


def test_scope_lock_is_audio_compatibility_only():
    from pathlib import Path

    source = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)
