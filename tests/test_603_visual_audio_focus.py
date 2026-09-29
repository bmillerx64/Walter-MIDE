from pathlib import Path

from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs603_visual_focus_uses_first_final_record_without_extreme(monkeypatch):
    rows = [{"symbol": "CYAB"}, {"symbol": "BGIN"}]
    monkeypatch.setattr(
        presentation_audio,
        "prioritized_extreme_event",
        lambda _rows: (None, None),
    )

    record, surface = presentation_audio.visual_audio_focus_record(rows)

    assert record["symbol"] == "CYAB"
    assert surface == "opportunity_first"


def test_gs603_visual_focus_prefers_rendered_extreme_banner(monkeypatch):
    rows = [{"symbol": "CYAB"}, {"symbol": "SDEV"}]
    extreme = rows[1]
    monkeypatch.setattr(
        presentation_audio,
        "prioritized_extreme_event",
        lambda _rows: (extreme, {"symbol": "SDEV", "label": "EXTREME MOVER"}),
    )

    record, surface = presentation_audio.visual_audio_focus_record(rows)

    assert record["symbol"] == "SDEV"
    assert surface == "extreme_banner"


def test_gs603_focus_is_scan_token_bound_and_detached():
    state = {
        "_walter_canonical_render_audio_focus": {
            "scan_token": "scan-1",
            "surface": "opportunity_first",
            "symbol": "CYAB",
            "record": {"symbol": "CYAB", "participation_score": 20},
        }
    }

    focused = presentation_audio.current_render_audio_focus(
        state,
        expected_scan_token="scan-1",
    )
    assert focused == [{"symbol": "CYAB", "participation_score": 20}]

    focused[0]["symbol"] = "MUTATED"
    assert state["_walter_canonical_render_audio_focus"]["record"]["symbol"] == "CYAB"

    assert presentation_audio.current_render_audio_focus(
        state,
        expected_scan_token="scan-2",
    ) == []


def test_gs603_native_market_event_audio_cannot_hijack_lower_symbol():
    rows = [{"symbol": "CYAB"}]
    events = [
        {"symbol": "MSGY", "event_type": "extreme_mover"},
        {"symbol": "CYAB", "event_type": "strategy_leader"},
    ]

    scoped = presentation_audio.operator_scoped_market_events(rows, events)

    assert [event["symbol"] for event in scoped] == ["CYAB"]
    assert presentation_audio.operator_scoped_market_events([], events) == events


def test_gs603_app_drives_semantic_audio_from_rendered_focus():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("_audio_scan_token = (")
    end = source.index("\ntab_names = [", start)
    block = source[start:end]

    assert "current_render_audio_focus(" in block
    assert "current_render_audio_event(" in block
    assert "_audio_focus_records" in block
    assert "escalation_alert_phrase(" not in block
    assert "scan_alert_phrase(" not in block
    assert "newly_entered_symbols(" not in block
    assert "Coiling." not in block
    assert "[WALTER AUDIO] canonical visual focus" in block
    assert "[WALTER AUDIO] canonical live phrase" in block


def test_gs603_authority_publishes_focus_only_from_primary_operator_renderer():
    source = (
        ROOT / "mide" / "authorities" / "presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert 'if attr == "render_walter_mission_control":' in source
    assert "_publish_render_audio_focus(ordered)" in source
    assert "operator_scoped_market_events(" in source


def test_gs603_scope_does_not_change_scanner_or_trading_authority():
    source = (
        ROOT / "mide" / "authorities" / "presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index('_RENDER_AUDIO_FOCUS_KEY =')
    end = source.index("\ndef final_enriched_opportunity_records(", start)
    focus_block = source[start:end]

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
    assert not any(token in focus_block for token in forbidden)
