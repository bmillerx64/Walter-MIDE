from copy import deepcopy

from mide.gs303_flight_recorder_authoritative_funnel import recorder_records


def _audit(stage, decision, reason="ok"):
    return {"stage": stage, "decision": decision, "reason": reason}


def test_architecture_audit_rehydrates_recorder_gate_fields():
    records = [{
        "symbol": "RUNR",
        "architecture_audit": [
            _audit("Participation Assessment", "Qualified", "participation measured"),
            _audit("Expansion Assessment", "Qualified", "Confluence 65"),
        ],
        "terminal_outcome": "Qualified and Ranked",
        "mission_rank": 1,
    }]

    result = recorder_records(records)[0]

    assert result["participation_gate"]["passed"] is True
    assert result["structure_gate"]["passed"] is True
    assert result["qualified_for_ranking"] is True
    assert result["participation_gate"]["source"] == "architecture_audit"


def test_participation_rejection_does_not_manufacture_structure_pass():
    result = recorder_records([{
        "symbol": "DROP",
        "architecture_audit": [
            _audit("Participation Assessment", "Rejected", "volume weak"),
        ],
        "terminal_outcome": "Rejected",
        "terminal_stage": "Participation Assessment",
    }])[0]

    assert result["participation_gate"]["passed"] is False
    assert result["participation_gate"]["failed_reasons"] == ["volume weak"]
    assert result["structure_gate"] == {}
    assert result["qualified_for_ranking"] is False


def test_architecture_audit_overrides_stale_legacy_false_fields_for_diagnostics():
    result = recorder_records([{
        "symbol": "LIVE",
        "participation_gate": {"passed": False},
        "structure_gate": {"passed": False},
        "qualified_for_ranking": False,
        "architecture_audit": [
            _audit("Participation Assessment", "Qualified"),
            _audit("Expansion Assessment", "Qualified"),
        ],
        "terminal_outcome": "Qualified and Ranked",
    }])[0]

    assert result["participation_gate"]["passed"] is True
    assert result["structure_gate"]["passed"] is True
    assert result["qualified_for_ranking"] is True


def test_legacy_records_without_architecture_audit_are_unchanged():
    record = {
        "symbol": "LEGACY",
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": False},
        "qualified_for_ranking": False,
    }
    assert recorder_records([record])[0] == record


def test_recorder_projection_never_mutates_authoritative_records():
    records = [{
        "symbol": "SAFE",
        "price": 1.23,
        "architecture_audit": [
            _audit("Participation Assessment", "Qualified"),
            _audit("Expansion Assessment", "Qualified"),
        ],
        "terminal_outcome": "Qualified and Ranked",
    }]
    before = deepcopy(records)

    projected = recorder_records(records)

    assert records == before
    assert projected is not records
    assert projected[0] is not records[0]
    assert projected[0]["price"] == 1.23
