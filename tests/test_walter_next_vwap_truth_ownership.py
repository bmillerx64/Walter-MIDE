"""Phase 5 ownership contract for numeric VWAP truth."""

from pathlib import Path

from mide.authorities import thesis_state
from mide import gs468_vwap_truth_veto as gs468


def test_gs468_is_a_compatibility_shim_to_thesis_state():
    assert gs468.current_vwap_truth is thesis_state.current_vwap_truth
    assert gs468.vwap_truth_state is thesis_state.vwap_truth_state
    assert gs468.install is thesis_state.install_vwap_truth


def test_numeric_vwap_truth_meaning_lives_in_thesis_state():
    authority = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs468_vwap_truth_veto.py").read_text(encoding="utf-8")

    assert "def current_vwap_truth(" in authority
    assert "def vwap_truth_state(" in authority
    assert "def install_vwap_truth(" in authority

    assert "def current_vwap_truth(" not in legacy
    assert "def vwap_truth_state(" not in legacy
    assert "def install(" not in legacy


def test_numeric_below_vwap_still_blocks_urgency_without_new_market_data():
    record = {
        "symbol": "JZXN",
        "price": 1.275,
        "vwap_value": 1.399,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "timeframes": {
            "1m": {"current_close": 1.281, "current_vwap": 1.393},
        },
    }
    truth = thesis_state.current_vwap_truth(record)
    assert truth["numeric_below"] is True
    assert truth["additional_market_data_requests"] == 0

    look_now = lambda _record: {
        "state": thesis_state.LOOK_NOW,
        "color": thesis_state.STATE_COLORS[thesis_state.LOOK_NOW],
        "reason": "attention",
        "next_step": "review",
        "attention_provenance": [],
        "evidence": [],
    }
    view = thesis_state.vwap_truth_state(look_now, record)
    assert view["state"] == thesis_state.DEVELOPING
    assert view["vwap_truth_veto"]["numeric_below"] is True
