from mide import gs529_entry_ready_shadow_calibration as gs529


def _trigger(st=False, participation=True, vwap=True, expansion=True):
    checks = [
        {"condition": "participation", "passed": participation},
        {"condition": "supertrend_flip", "passed": st},
        {"condition": "vwap", "passed": vwap},
        {"condition": "expansion_beginning", "passed": expansion},
    ]
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def test_shadow_recovers_only_missing_st_lock(monkeypatch):
    monkeypatch.setattr(
        gs529,
        "_fresh_progression",
        lambda _r: {
            "active": True,
            "new_rung": "1m",
            "highest_rung": "1m",
            "fresh_rungs": ["30s", "1m"],
            "source": "test",
        },
    )
    result = gs529.shadow_entry_calibration(
        {},
        trigger=_trigger(st=False),
        structure_gate={"passed": True},
    )
    assert result["canonical_entry_ready"] is False
    assert result["shadow_entry_ready"] is True
    assert result["recovered_by_progression"] is True
    assert result["shadow_st_substitution_used"] is True


def test_shadow_does_not_override_other_failed_locks(monkeypatch):
    monkeypatch.setattr(
        gs529,
        "_fresh_progression",
        lambda _r: {"active": True, "new_rung": "3m", "fresh_rungs": ["1m", "3m"]},
    )
    result = gs529.shadow_entry_calibration(
        {},
        trigger=_trigger(st=False, vwap=False),
        structure_gate={"passed": True},
    )
    assert result["shadow_entry_ready"] is False
    assert "vwap" in result["shadow_failed_conditions"]


def test_shadow_requires_structure(monkeypatch):
    monkeypatch.setattr(
        gs529,
        "_fresh_progression",
        lambda _r: {"active": True, "new_rung": "1m", "fresh_rungs": ["30s", "1m"]},
    )
    result = gs529.shadow_entry_calibration(
        {},
        trigger=_trigger(st=False),
        structure_gate={"passed": False},
    )
    assert result["shadow_trigger_passed"] is True
    assert result["shadow_entry_ready"] is False


def test_no_progression_means_no_shadow_relaxation(monkeypatch):
    monkeypatch.setattr(
        gs529,
        "_fresh_progression",
        lambda _r: {"active": False, "new_rung": None, "fresh_rungs": []},
    )
    result = gs529.shadow_entry_calibration(
        {},
        trigger=_trigger(st=False),
        structure_gate={"passed": True},
    )
    assert result["shadow_entry_ready"] is False
    assert result["trading_authority_changed"] is False


def test_runtime_persists_shadow_without_using_it_for_entry_authority():
    from pathlib import Path

    scanner = Path("mide/scanner_v2.py").read_text(encoding="utf-8")
    recorder = Path("mide/flight_recorder.py").read_text(encoding="utf-8")

    assert "entry_ready_shadow = shadow_entry_calibration(" in scanner
    assert '"gs529_entry_ready_shadow": entry_ready_shadow' in scanner
    assert "entry_qualified = qualified_for_entry(" in scanner
    assert "entry_ready_shadow" not in scanner[
        scanner.index("entry_qualified = qualified_for_entry("):
        scanner.index("record[\"qualified_for_entry\"] = entry_qualified")
    ]
    assert '"gs529_entry_ready_shadow": (record or {}).get(' in recorder
