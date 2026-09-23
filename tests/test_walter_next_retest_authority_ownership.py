"""Phase 8 ownership contract for 3m retest truth, memory, and discipline."""

from pathlib import Path

from mide import gs493_3m_st_retest_truth as gs493
from mide import gs514_retest_event_memory as gs514
from mide import gs515_thesis_trigger_discipline as gs515
from mide.authorities import market_evidence, thesis_state


def test_gs493_facade_delegates_to_authoritative_components():
    record = {
        "price": 1.10,
        "timeframes": {
            "3m": {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_close": 1.10,
                "current_above_vwap": True,
                "st_vwap_line_cross": {
                    "latest_supertrend_value": 1.00,
                    "latest_vwap_value": 1.05,
                },
            }
        },
    }
    assert gs493.three_minute_st_retest_truth(record) == market_evidence.three_minute_st_retest_truth(record)


def test_gs514_and_gs515_are_compatibility_facades():
    event = {"active_memory": True}
    record = {
        "vwap_relation": "above",
        "vwap_distance_pct": 0.5,
        "timeframes": {
            "30s": {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
            },
            "1m": {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
            },
        },
    }
    assert gs514.discipline_sequence(record, event) == thesis_state.discipline_sequence(record, event)

    view = {
        "state": "DEVELOPING",
        "discipline_sequence": {
            "state": "THESIS_HELD_TRIGGER_INCOMPLETE",
            "three_minute_retest_held": True,
            "vwap_acceptance": False,
            "thirty_second_repaired": True,
            "one_minute_repaired": False,
        },
        "evidence": [],
        "next_step": "",
    }
    assert gs515.emphasize_discipline(view) == thesis_state.emphasize_discipline(view)


def test_retest_evidence_and_meaning_have_separate_authoritative_homes():
    evidence_source = Path("mide/authorities/market_evidence.py").read_text(encoding="utf-8")
    thesis_source = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")

    assert "def base_three_minute_st_retest_truth(" in evidence_source
    assert "def latest_held_retest(" in evidence_source
    assert "def reconstruct_three_minute_retest(" in evidence_source
    assert "def memory_adjusted_retest_truth(" in evidence_source

    assert "def base_state_with_3m_st_truth(" in thesis_source
    assert "def discipline_sequence(" in thesis_source
    assert "def retest_memory_state(" in thesis_source
    assert "def emphasize_discipline(" in thesis_source


def test_historical_modules_are_explicit_facades():
    for path in (
        "mide/gs493_3m_st_retest_truth.py",
        "mide/gs514_retest_event_memory.py",
        "mide/gs515_thesis_trigger_discipline.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "Compatibility facade" in source
