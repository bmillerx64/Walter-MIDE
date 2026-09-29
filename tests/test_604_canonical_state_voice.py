from pathlib import Path

from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs604_canonical_voice_matches_visible_opportunity_state(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    record = {
        "symbol": "NIVF",
        "quality_grade": "C",
        "quality_score": 61,
    }
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": (
                "Price is still near VWAP, but it is already 6.2% above the "
                "bullish 3m SuperTrend line. The move is no longer a fresh "
                "Developing setup."
            ),
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    phrase = presentation_audio.canonical_opportunity_audio_phrase([record])

    assert phrase.startswith("NIVF. CHASE / WAIT.")
    assert "6.2% above the bullish 3m SuperTrend line" in phrase
    assert "Grade" not in phrase
    assert "Score" not in phrase
    assert "61" not in phrase


def test_gs604_look_now_voice_includes_same_context(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    record = {"symbol": "CYAB"}
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "LOOK NOW",
            "reason": "Fresh structure is maturing across the lower timeframes.",
        },
    )
    monkeypatch.setattr(
        unified,
        "look_now_context",
        lambda _record, _view: "STRUCTURE MATURING",
    )

    phrase = presentation_audio.canonical_opportunity_audio_phrase([record])

    assert phrase == (
        "CYAB. LOOK NOW. STRUCTURE MATURING. "
        "Fresh structure is maturing across the lower timeframes."
    )


def test_gs604_live_audio_path_no_longer_uses_legacy_scan_alert_phrase():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("_audio_scan_token = (")
    end = source.index("\ntab_names = [", start)
    block = source[start:end]

    assert "current_render_audio_event(" in block
    assert "scan_alert_phrase(" not in block
    assert "escalation_alert_phrase(" not in block


def test_gs604_legacy_scan_phrase_may_remain_for_non_live_compatibility():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "def scan_alert_phrase(records: list[dict]) -> str:" in source
    live_start = source.index("_audio_scan_token = (")
    assert source.index("def scan_alert_phrase(records: list[dict]) -> str:") < live_start


def test_gs604_scope_is_presentation_audio_only():
    source = (
        ROOT / "mide" / "authorities" / "presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("def canonical_opportunity_audio_phrase(")
    end = source.index("\ndef operator_scoped_market_events(", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "PROCESS_SCAN_WATCHDOG",
        "note_scan_started(",
    )
    assert not any(token in block for token in forbidden)
