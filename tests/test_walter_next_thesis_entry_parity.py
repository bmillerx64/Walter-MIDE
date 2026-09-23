"""Frozen behavioral parity cases for the first Walter Next semantic consolidation.

These cases deliberately exercise the authoritative seams after the same late-runtime
installer boundary used by app.py.  They are not new strategy rules.  They snapshot
representative behavior that already exists at the frozen v3 baseline so Thesis/State
and Entry Authority can be consolidated without silently changing Walter.
"""

from __future__ import annotations

from mide import startup

# app.py invokes this from log_startup("entering app.py") before importing the
# authority seams.  Mirror that production ordering here.
startup.ensure_late_runtime_installers()

from mide.authorities import entry_authority as entry
from mide.authorities import thesis_state as thesis


def _opportunity_record(**updates):
    record = {
        "symbol": "PARITY",
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_surge_score": 80.0,
        "participation_score": 80.0,
        "expansion_quality": 65.0,
        "volume_acceleration": 1.2,
        "dollar_flow_acceleration": 1.2,
        "discovery_reasons": ["Webull native: day_gainers"],
    }
    record.update(updates)
    return record


def _continuation_record(**updates):
    record = {
        "symbol": "SBFM",
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "supertrend_flipped_last_10m": False,
        "vwap_distance_pct": 1.12,
        "strengthening_vwap_gate": {"distance_pct": 1.12},
        "expansion_quality": 71.0,
        "trend_confirmation_sequence": {
            "progression_count": 4,
            "conflict_count": 0,
        },
        "participation_surge_diagnostics": {
            "participation_score": 79.0,
            "expansion_quality": 71.0,
            "volume_acceleration": {"3m": 3.89},
            "dollar_flow_acceleration": {"3m": 3.94},
        },
    }
    record.update(updates)
    return record


def _retest_record(**updates):
    record = {
        "price": 1.00,
        "vwap_distance_pct": 0.5,
        "participation_surge_diagnostics": {"participation_score": 67},
        "expansion_quality": 63,
        "vwap_relation": "above",
        "timeframe_alignment": {
            "30s": {
                "above_vwap": True,
                "supertrend_bullish": True,
                "supertrend_value": 0.95,
                "vwap_value": 0.99,
            }
        },
        "timeframes": {
            "30s": {
                "current_close": 1.00,
                "supertrend": True,
            },
            "1m": {
                "current_close": 1.00,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
            },
        },
        "multitimeframe_maturation": {
            "three_minute_st_retest_event": {
                "available": True,
                "active_memory": True,
            }
        },
    }
    record.update(updates)
    return record


def _trigger(*passed):
    names = ("participation", "supertrend_flip", "vwap", "expansion_beginning")
    checks = []
    for name, value in zip(names, passed):
        checks.append({
            "condition": name,
            "passed": value,
            "passed_reason": f"{name} pass",
            "failed_reason": f"{name} failed",
        })
    return {"passed": all(passed), "checks": checks}


def test_parity_developing_state_is_preserved():
    view = thesis.opportunity_state(
        _opportunity_record(
            participation_surge_score=45,
            expansion_quality=70,
            volume_acceleration=0.8,
            dollar_flow_acceleration=0.8,
        )
    )
    assert view["state"] == thesis.DEVELOPING


def test_parity_look_now_state_is_preserved_for_current_mover_flow():
    view = thesis.opportunity_state(
        _opportunity_record(
            symbol="VIOT",
            participation_surge_score=31.6,
            participation_score=31.6,
            expansion_quality=40,
            volume_acceleration=0.50,
            dollar_flow_acceleration=1.74,
            vwap_distance_pct=1.41,
        )
    )
    assert view["state"] == thesis.LOOK_NOW


def test_parity_extended_symbol_stays_chase_wait():
    view = thesis.opportunity_state(_opportunity_record(vwap_distance_pct=4.5))
    assert view["state"] == thesis.CHASE_WAIT
    assert "extended" in view["reason"].lower()


def test_parity_halt_outranks_every_other_state():
    view = thesis.opportunity_state(
        _opportunity_record(is_halted=True, vwap_distance_pct=8.0)
    )
    assert view["state"] == thesis.HALTED


def test_parity_watch_for_entry_state_is_preserved():
    view = thesis.opportunity_state(_opportunity_record())
    assert view["state"] == thesis.WATCH_FOR_ENTRY


def test_parity_true_entry_ready_requires_executable_authority():
    record = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": True,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, True, True, True),
    }
    assert entry.canonical_candidate_status(record) == "Entry Ready"
    assert entry.entry_contract(record)["label"] == "ENTRY READY"


def test_parity_false_legacy_entry_ready_never_becomes_authority():
    record = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": False,
        "structure_gate": {"passed": True},
        "trigger_diagnostics": _trigger(True, True, False, True),
    }
    assert entry.canonical_candidate_status(record) == "Strengthening"
    contract = entry.entry_contract(record)
    assert contract["label"] == "SETTING UP · 3/4 TRIGGER LOCKS"
    assert contract["legacy_false_entry_ready"] is True


def test_parity_continuation_reignition_can_satisfy_st_lock():
    result = entry.trigger_diagnostics(_continuation_record())
    checks = {row["condition"]: row for row in result["checks"]}
    assert checks["supertrend_flip"]["passed"] is True
    assert result["continuation_reignition"]["active"] is True
    assert result["passed"] is True


def test_parity_continuation_reignition_cannot_override_extension():
    record = _continuation_record(vwap_distance_pct=2.1)
    record["strengthening_vwap_gate"]["distance_pct"] = 2.1
    result = entry.trigger_diagnostics(record)
    assert result["continuation_reignition"]["active"] is False
    assert result["passed"] is False
    assert "vwap" in result["failed_conditions"]


def test_parity_retest_shadow_preserves_entry_window_and_no_authority_change():
    result = entry.retest_entry_shadow(_retest_record())
    assert result["shadow_entry_ready"] is True
    assert result["failed_conditions"] == []
    assert result["trading_authority_changed"] is False


def test_parity_retest_shadow_preserves_antichase():
    result = entry.retest_entry_shadow(_retest_record(vwap_distance_pct=6.0))
    assert result["shadow_entry_ready"] is False
    assert "vwap_entry_window" in result["failed_conditions"]
    assert result["trading_authority_changed"] is False
