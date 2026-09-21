from pathlib import Path

from mide import gs493_3m_st_retest_truth as gs493
from mide import gs515_thesis_trigger_discipline as gs515


def _view(sequence_state, **flags):
    sequence = {
        "state": sequence_state,
        "three_minute_retest_held": True,
        "vwap_acceptance": flags.get("vwap", False),
        "thirty_second_repaired": flags.get("thirty", False),
        "one_minute_repaired": flags.get("one", False),
        "lower_timeframe_repair_complete": flags.get("complete", False),
    }
    return {
        "state": "DEVELOPING",
        "color": "#60a5fa",
        "reason": "Old explanation.",
        "next_step": "Existing guidance.",
        "evidence": [
            {"label": "VWAP", "passed": False, "detail": "Not above"},
            {"label": "SuperTrend", "passed": True, "detail": "Bullish"},
        ],
        "discipline_sequence": sequence,
    }


def test_incomplete_sequence_says_trigger_not_earned_without_state_promotion():
    view = _view(
        "THESIS_HELD_TRIGGER_INCOMPLETE",
        vwap=False,
        thirty=True,
        one=False,
    )
    result = gs515.emphasize_discipline(view)

    assert result["state"] == "DEVELOPING"
    assert result["color"] == "#60a5fa"
    assert result["discipline_ready"] is False
    assert result["discipline_label"] == "THESIS VALIDATED · TRIGGER NOT EARNED"
    assert result["reason"] == "Old explanation."
    assert result["next_step"].startswith("THESIS VALIDATED · TRIGGER NOT EARNED")
    assert result["evidence"][0] == {
        "label": "Entry sequence",
        "passed": False,
        "detail": "3m retest ✓ · VWAP ○ · 30s ✓ · 1m ○",
    }


def test_repaired_sequence_still_does_not_change_existing_opportunity_state():
    view = _view(
        "THESIS_HELD_TRIGGER_REPAIRED",
        vwap=True,
        thirty=True,
        one=True,
        complete=True,
    )
    result = gs515.emphasize_discipline(view)

    assert result["state"] == "DEVELOPING"
    assert result["discipline_ready"] is True
    assert result["discipline_label"] == "THESIS VALIDATED · LOWER-TF REPAIR PRESENT"
    assert result["reason"] == "Old explanation."
    assert "full entry/readiness rules still control" in result["next_step"]
    assert result["evidence"][0]["passed"] is True
    assert result["evidence"][0]["detail"] == "3m retest ✓ · VWAP ✓ · 30s ✓ · 1m ✓"


def test_no_discipline_sequence_is_untouched():
    view = {
        "state": "CHASE / WAIT",
        "reason": "Extended.",
        "evidence": [],
    }
    assert gs515.emphasize_discipline(view) == view


def test_install_wraps_gs493_state_helper_only_once():
    before = gs493.state_with_3m_st_truth
    gs515.install()
    first = gs493.state_with_3m_st_truth
    gs515.install()
    second = gs493.state_with_3m_st_truth

    assert first is second
    assert getattr(first, "_walter_gs515_thesis_trigger_discipline", False) is True
    assert first is not before or getattr(before, "_walter_gs515_thesis_trigger_discipline", False)


def test_scope_lock_is_presentation_only():
    source = Path("mide/gs515_thesis_trigger_discipline.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        "play_alert(",
        "TONE_PATTERNS",
    )
    assert not any(token in source for token in forbidden)
    assert "PRESENTATION_DISCIPLINE_ONLY" in source


def test_install_order_is_after_gs514_memory():
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    assert chain.index("install_gs514()") < chain.index("install_gs515()")
