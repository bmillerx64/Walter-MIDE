from mide.readiness_audit import readiness_consistency


def test_flags_workflow_ready_when_current_trigger_is_not_ready():
    result = readiness_consistency({
        "candidate_status": "Entry Ready",
        "trigger_diagnostics": {"passed": False},
    })
    assert result["workflow_entry_ready"] is True
    assert result["current_entry_evidence_known"] is True
    assert result["current_entry_evidence_ready"] is False
    assert result["entry_readiness_mismatch"] is True


def test_does_not_flag_when_workflow_and_current_evidence_agree():
    result = readiness_consistency({
        "candidate_status": "Entry Ready",
        "trigger_diagnostics": {"passed": True},
    })
    assert result["entry_readiness_mismatch"] is False


def test_unknown_current_evidence_is_not_invented_as_failure():
    result = readiness_consistency({"candidate_status": "Entry Ready"})
    assert result["current_entry_evidence_known"] is False
    assert result["current_entry_evidence_ready"] is None
    assert result["entry_readiness_mismatch"] is False


def test_non_ready_workflow_state_is_not_a_mismatch():
    result = readiness_consistency({
        "candidate_status": "Strengthening",
        "trigger_diagnostics": {"passed": False},
    })
    assert result["workflow_entry_ready"] is False
    assert result["entry_readiness_mismatch"] is False
