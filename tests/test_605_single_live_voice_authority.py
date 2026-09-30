from pathlib import Path

from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs605_current_card_state_is_the_spoken_state(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": "Price is extended; wait for a constructive reset.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    state = {
        "_walter_canonical_render_audio_focus": {
            "scan_token": "scan-2",
            "surface": "opportunity_first",
            "symbol": "NIVF",
            "state_label": "CHASE / WAIT",
            "event": None,
            "record": {"symbol": "NIVF"},
        },
        "_walter_previous_render_audio_focus": {
            "scan_token": "scan-1",
            "surface": "opportunity_first",
            "symbol": "CYAB",
            "state_label": "DEVELOPING",
            "record": {"symbol": "CYAB"},
        },
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )

    assert event["triggered"] is True
    assert event["symbol"] == "NIVF"
    assert event["state_label"] == "CHASE / WAIT"
    assert event["phrase"].startswith("NIVF. CHASE / WAIT.")
    assert "LOOK NOW" not in event["phrase"]
    assert "WATCH NOW" not in event["phrase"]


def test_gs605_offscreen_symbol_cannot_be_spoken(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "DEVELOPING",
            "reason": "Current top opportunity remains under review.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    state = {
        "_walter_canonical_render_audio_focus": {
            "scan_token": "scan-9",
            "surface": "opportunity_first",
            "symbol": "CYAB",
            "state_label": "DEVELOPING",
            "event": None,
            "record": {"symbol": "CYAB"},
        },
        "_walter_previous_render_audio_focus": {
            "scan_token": "scan-8",
            "surface": "opportunity_first",
            "symbol": "BGIN",
            "state_label": "CHASE / WAIT",
            "record": {"symbol": "BGIN"},
        },
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-9",
    )

    assert event["symbol"] == "CYAB"
    assert event["phrase"].startswith("CYAB. DEVELOPING.")
    assert "BGIN" not in event["phrase"]
    assert "MSGY" not in event["phrase"]


def test_gs605_unchanged_rendered_focus_does_not_repeat_voice(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": "CHASE / WAIT",
            "reason": "Still extended.",
        },
    )
    monkeypatch.setattr(unified, "look_now_context", lambda _record, _view: "")

    state = {
        "_walter_canonical_render_audio_focus": {
            "scan_token": "scan-2",
            "surface": "opportunity_first",
            "symbol": "NIVF",
            "state_label": "CHASE / WAIT",
            "event": None,
            "record": {"symbol": "NIVF"},
        },
        "_walter_previous_render_audio_focus": {
            "scan_token": "scan-1",
            "surface": "opportunity_first",
            "symbol": "NIVF",
            "state_label": "CHASE / WAIT",
            "record": {"symbol": "NIVF"},
        },
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-2",
    )

    assert event["triggered"] is False
    assert event["reason"] == "rendered_focus_unchanged"


def test_gs605_extreme_banner_voice_matches_banner_label():
    state = {
        "_walter_canonical_render_audio_focus": {
            "scan_token": "scan-x",
            "surface": "extreme_banner",
            "symbol": "SDEV",
            "state_label": "EXTREME MOVER · DO NOT CHASE",
            "record": {"symbol": "SDEV"},
            "event": {
                "symbol": "SDEV",
                "label": "EXTREME MOVER · DO NOT CHASE",
                "pct_change": 103.8,
                "guidance": "Wait for a constructive reset before reconsidering.",
            },
        },
        "_walter_previous_render_audio_focus": {},
    }

    event = presentation_audio.current_render_audio_event(
        state,
        expected_scan_token="scan-x",
    )

    assert event["triggered"] is True
    assert "EXTREME MOVER · DO NOT CHASE" in event["phrase"]
    assert "LOOK NOW" not in event["phrase"]


def test_gs605_live_app_has_no_legacy_semantic_voice_producer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("_audio_scan_token = (")
    end = source.index("\n# GS601: consume process-scan audio only after the entire dashboard render", start)
    block = source[start:end]

    forbidden = (
        "escalation_alert_phrase(",
        "scan_alert_phrase(",
        "newly_entered_symbols(",
        "Coiling.",
        "operator_attention_audio_phrase(",
        "native_market_event_audio_phrase(",
        "look_now_alert_phrase(",
    )
    assert not any(token in block for token in forbidden)
    assert "current_render_audio_event(" in block
    assert "audio_triggered = bool(_audio_event.get(\"triggered\"))" in block


def test_gs605_scope_does_not_change_trading_authority():
    source = (
        ROOT / "mide" / "authorities" / "presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("def current_render_audio_event(")
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
        "request_scan(",
        "note_scan_started(",
    )
    assert not any(token in block for token in forbidden)
