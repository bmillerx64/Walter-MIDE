from mide.gs353_entry_lock_clarity import entry_lock_snapshot, entry_locks_markup


def _record(*, st=True, vwap=True, participation=True, expansion=False, structure=True, entry=False):
    checks = []
    values = {
        "supertrend_flip": st,
        "vwap": vwap,
        "participation": participation,
        "expansion_beginning": expansion,
    }
    for condition, passed in values.items():
        checks.append({
            "condition": condition,
            "passed": passed,
            "passed_reason": f"{condition} pass",
            "failed_reason": f"{condition} waiting",
        })
    return {
        "symbol": "GYGY",
        "structure_gate": {"passed": structure},
        "trigger_diagnostics": {"passed": all(values.values()), "checks": checks},
        "qualified_for_entry": entry,
        "candidate_status": "Entry Ready" if entry else "Strengthening",
    }


def test_three_of_four_with_structure_is_armed_not_entry_ready():
    snap = entry_lock_snapshot(_record())
    assert snap["passed_count"] == 3
    assert snap["armed"] is True
    assert snap["entry_ready"] is False
    assert snap["state"] == "ARMED · ONE LOCK REMAINING"


def test_all_trigger_locks_do_not_claim_entry_without_existing_entry_contract():
    snap = entry_lock_snapshot(_record(expansion=True, entry=False))
    assert snap["trigger_passed"] is True
    assert snap["entry_ready"] is False
    assert snap["state"] == "DEVELOPING"


def test_existing_entry_ready_contract_renders_full_ready_state():
    record = _record(expansion=True, entry=True)
    snap = entry_lock_snapshot(record)
    assert snap["entry_ready"] is True
    assert snap["state"] == "ENTRY READY"
    markup = entry_locks_markup(record)
    assert "ENTRY READY" in markup
    assert "ST FLIP" in markup
    assert "VWAP" in markup
    assert "PARTICIPATION" in markup
    assert "EXPANSION" in markup


def test_structure_failure_prevents_armed_label_even_with_three_trigger_locks():
    snap = entry_lock_snapshot(_record(structure=False))
    assert snap["passed_count"] == 3
    assert snap["armed"] is False
    assert snap["state"] == "DEVELOPING"
