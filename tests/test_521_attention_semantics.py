from pathlib import Path

from mide import gs310_unified_opportunity_state as unified


def test_avat_style_fresh_maturation_is_labeled_structure_maturing(monkeypatch):
    from mide import gs455_early_ignition_3m_confirmation as gs455

    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: {"active": record.get("symbol") == "AVAT"},
    )
    record = {"symbol": "AVAT"}
    view = {"state": unified.LOOK_NOW, "reason": "EARLY IGNITION: 30s -> 1m"}

    assert unified.look_now_context(record, view) == "STRUCTURE MATURING"


def test_sdst_style_generic_attention_is_not_presented_like_structure_maturation(monkeypatch):
    from mide import gs455_early_ignition_3m_confirmation as gs455

    monkeypatch.setattr(gs455, "progression_signal", lambda record: {"active": False})
    record = {"symbol": "SDST"}
    view = {
        "state": unified.LOOK_NOW,
        "reason": "A current attention trigger says this symbol deserves a chart review.",
    }

    assert unified.look_now_context(record, view) == "MARKET ATTENTION"


def test_reference_data_blocked_attention_keeps_its_distinct_context():
    record = {"symbol": "JZ", "reference_data_blocked_awareness": True}
    view = {"state": unified.LOOK_NOW, "reason": "reference data unresolved"}

    assert unified.look_now_context(record, view) == "REFERENCE DATA BLOCKED"


def test_non_look_now_states_receive_no_attention_context():
    record = {"symbol": "NCPL"}
    view = {"state": unified.DEVELOPING, "reason": "still developing"}

    assert unified.look_now_context(record, view) == ""


def test_scope_lock_is_presentation_semantics_only():
    source = Path("mide/gs310_unified_opportunity_state.py").read_text(encoding="utf-8")
    assert "def look_now_context" in source
    forbidden = (
        "mission_rank =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_quality =",
        "place_order(",
        "submit_order(",
    )
    block = source[source.index("def look_now_context"):source.index("def _confidence_cue")]
    assert not any(token in block for token in forbidden)
