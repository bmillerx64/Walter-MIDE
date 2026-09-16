from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs468_vwap_truth_veto as gs468


def _look_now(_record):
    return {
        "state": unified.LOOK_NOW,
        "color": unified.STATE_COLORS[unified.LOOK_NOW],
        "reason": "A current attention trigger says this symbol deserves a chart review.",
        "next_step": "Open the chart now.",
        "attention_provenance": ["TEST"],
        "evidence": [
            {"label": "VWAP", "passed": True, "detail": "Above / within 2%"},
        ],
    }


def _developing(_record):
    return {
        "state": unified.DEVELOPING,
        "color": unified.STATE_COLORS[unified.DEVELOPING],
        "reason": "test",
        "next_step": "test",
        "attention_provenance": [],
    }


def test_jzxn_like_numeric_below_vwap_vetoes_look_now():
    record = {
        "symbol": "JZXN",
        "price": 1.275,
        "vwap_value": 1.399,
        # Reproduce the contradiction seen live: categorical fields say above even
        # though the current numeric pair proves otherwise.
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "timeframes": {
            "1m": {"current_close": 1.281, "current_vwap": 1.393},
        },
    }

    truth = gs468.current_vwap_truth(record)
    assert truth["numeric_below"] is True
    assert set(truth["below_sources"]) == {
        "snapshot_vs_primary_vwap",
        "1m_close_vs_primary_vwap",
    }

    view = gs468.vwap_truth_state(_look_now, record)
    assert view["state"] == unified.DEVELOPING
    assert "below VWAP" in view["reason"]
    assert view["vwap_truth_veto"]["numeric_below"] is True


def test_numeric_below_copy_corrects_relation_and_distance_without_mutating_record():
    record = {
        "symbol": "TEST",
        "price": 1.00,
        "vwap_value": 1.10,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.5,
    }
    truth = gs468.current_vwap_truth(record)
    corrected = gs468._numeric_below_record(record, truth)

    assert corrected is not record
    assert corrected["vwap_relation"] == "below"
    assert corrected["vwap_distance_pct"] < 0
    assert record["vwap_relation"] == "above"
    assert record["vwap_distance_pct"] == 0.5


def test_one_minute_numeric_below_is_enough_to_veto_stale_top_level_category():
    record = {
        "symbol": "ONE",
        "vwap_relation": "above",
        "vwap_distance_pct": 0.4,
        "timeframes": {
            "1m": {"current_close": 0.96, "current_vwap": 1.00},
        },
    }
    truth = gs468.current_vwap_truth(record)
    assert truth["numeric_below"] is True
    assert truth["below_sources"] == ["1m_close_vs_primary_vwap"]
    assert gs468.vwap_truth_state(_look_now, record)["state"] == unified.DEVELOPING


def test_current_numeric_above_preserves_existing_look_now_semantics():
    record = {
        "symbol": "ABOVE",
        "price": 1.02,
        "vwap_value": 1.00,
        "vwap_relation": "above",
        "vwap_distance_pct": 2.0,
        "timeframes": {
            "1m": {"current_close": 1.01, "current_vwap": 1.00},
        },
    }
    original = _look_now(record)
    result = gs468.vwap_truth_state(lambda _record: original, record)
    assert result is original
    assert result["state"] == unified.LOOK_NOW


def test_missing_numeric_pairs_do_not_rewrite_fresh_event_contract():
    record = {
        "symbol": "NEWS",
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "headline": "Fresh material event",
    }
    truth = gs468.current_vwap_truth(record)
    assert truth["numeric_below"] is False
    original = _look_now(record)
    assert gs468.vwap_truth_state(lambda _record: original, record) is original


def test_existing_non_urgent_state_is_preserved_when_no_numeric_contradiction():
    record = {"symbol": "DEV", "price": 1.01, "vwap_value": 1.00}
    original = _developing(record)
    assert gs468.vwap_truth_state(lambda _record: original, record) is original


def test_gs468_is_after_gs467_at_final_state_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs468_vwap_truth_veto" in source
    assert source.index("_install_gs467()") < source.index("_install_gs468()")


def test_gs468_scope_lock_is_presentation_truth_only():
    source = Path("mide/gs468_vwap_truth_veto.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "PARTICIPATION_MIN_",
        "NEAR_ST_LINE_PCT =",
        "LOOK_NOW_MAX_VWAP",
    )
    for token in forbidden:
        assert token not in source
