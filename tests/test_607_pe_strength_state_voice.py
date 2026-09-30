from pathlib import Path

from mide.authorities import presentation_audio
from mide import gs310_unified_opportunity_state as unified


def _record(symbol="CNTB", participation=80, expansion=68):
    return {
        "symbol": symbol,
        "participation_surge_score": participation,
        "expansion_quality": expansion,
    }


def test_gs607_visible_description_restores_combined_pe_strength():
    record = _record()
    view = {
        "state": unified.WATCH_FOR_ENTRY,
        "reason": "VWAP, trend, participation, and expansion are aligned now.",
        "pe_strength_score": 74.0,
    }

    assert presentation_audio.opportunity_description_line(record, view) == (
        "P/E Strength 74/100 · "
        "VWAP, trend, participation, and expansion are aligned now."
    )


def test_gs607_description_computes_pe_when_view_metadata_is_absent():
    record = _record(participation=85, expansion=62)
    view = {"reason": "Constructive current setup."}

    assert presentation_audio.opportunity_description_line(record, view) == (
        "P/E Strength 74/100 · Constructive current setup."
    )


def test_gs607_state_reason_stays_clean_to_prevent_warm_wrapper_nesting():
    record = _record(participation=85, expansion=62)

    def original(_record):
        return {
            "state": unified.WATCH_FOR_ENTRY,
            "color": "#4ade80",
            "reason": "VWAP, trend, participation, and expansion are aligned now.",
        }

    view = presentation_audio.state_with_pe_strength(original, record)

    assert view["pe_strength_score"] == 73.5
    assert view["reason"] == (
        "VWAP, trend, participation, and expansion are aligned now."
    )
    assert "P/E Strength" not in view["reason"]


def test_gs607_canonical_live_voice_speaks_state_pe_and_reason(monkeypatch):
    record = _record()

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": unified.WATCH_FOR_ENTRY,
            "reason": "VWAP, trend, participation, and expansion are aligned now.",
            "pe_strength_score": 74.0,
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    phrase = presentation_audio.canonical_opportunity_audio_phrase([record])

    assert phrase == (
        "CNTB. WATCH FOR ENTRY. P E strength 74. "
        "VWAP, trend, participation, and expansion are aligned now."
    )


def test_gs607_state_renderers_use_canonical_description_line():
    source = Path("mide/gs310_unified_opportunity_state.py").read_text(
        encoding="utf-8"
    )

    assert "def _description_line(record: dict, view: dict) -> str:" in source
    assert source.count("_description_line(record, view)") >= 3
    assert "recommendation-message'>{html.escape(view['reason'])}" not in source


def test_gs607_is_presentation_audio_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    start = authority.index("def pe_strength_display_value")
    end = authority.index("def _pe_halted", start)
    block = authority[start:end]

    forbidden = (
        "qualified_for_entry =",
        "mission_rank =",
        "participation_surge_score =",
        "expansion_quality =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)
