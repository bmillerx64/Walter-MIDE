from mide import gs528_canonical_entry_ready as gs528


def _trigger(*passed):
    checks = []
    names = ("participation", "supertrend_flip", "vwap", "expansion_beginning")
    for name, value in zip(names, passed):
        checks.append({
            "condition": name,
            "passed": value,
            "passed_reason": f"{name} pass",
            "failed_reason": f"{name} failed",
        })
    return {"passed": all(passed), "checks": checks}


def test_true_entry_ready_requires_qualified_for_entry():
    record = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": True,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, True, True, True),
    }
    contract = gs528.entry_contract(record)
    assert contract["label"] == "ENTRY READY"
    assert contract["legacy_false_entry_ready"] is False


def test_false_legacy_entry_ready_is_explicitly_setting_up():
    record = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": False,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, True, False, True),
    }
    contract = gs528.entry_contract(record)
    assert contract["label"] == "SETTING UP · 3/4 TRIGGER LOCKS"
    assert contract["legacy_false_entry_ready"] is True
    assert "vwap failed" in contract["blockers"]


def test_exact_blocker_is_exposed_on_opportunity_state():
    record = {
        "candidate_status": "Strengthening",
        "qualified_for_entry": False,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, False, True, True),
    }
    base = {
        "state": "DEVELOPING",
        "color": "#60a5fa",
        "reason": "Constructive setup.",
        "next_step": "Continue monitoring.",
        "evidence": [],
        "attention_provenance": [],
    }
    result = gs528.state_with_entry_contract(lambda _record: base, record)
    assert result["reason"].startswith("SETTING UP · 3/4 TRIGGER LOCKS:")
    assert "Entry blocker: supertrend_flip failed" in result["next_step"]


def test_entry_contract_never_promotes_qualification():
    record = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": False,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, True, True, False),
    }
    base = {
        "state": "LOOK NOW",
        "color": "#facc15",
        "reason": "Market attention.",
        "next_step": "Review chart.",
        "evidence": [],
        "attention_provenance": [],
    }
    result = gs528.state_with_entry_contract(lambda _record: base, record)
    assert record["qualified_for_entry"] is False
    assert result["state"] == "LOOK NOW"
    assert result["entry_contract"]["qualified_for_entry"] is False


def test_canonical_candidate_status_never_invents_entry_ready():
    assert gs528.canonical_candidate_status({}) == "Strengthening"
    assert gs528.canonical_candidate_status({"candidate_status": "Entry Ready", "qualified_for_entry": False}) == "Strengthening"
    assert gs528.canonical_candidate_status({"candidate_status": "Watching", "qualified_for_entry": False}) == "Watching"
    assert gs528.canonical_candidate_status({"qualified_for_entry": True}) == "Entry Ready"


def test_runtime_fallbacks_no_longer_manufacture_entry_ready():
    from pathlib import Path

    app = Path("app.py").read_text(encoding="utf-8")
    engine = Path("mide/decision_engine.py").read_text(encoding="utf-8")
    assert 'item.get("candidate_status", "Entry Ready")' not in app
    assert 'record.get("candidate_status", "Entry Ready")' not in engine
    assert '"entry_ready": sum(' in app
