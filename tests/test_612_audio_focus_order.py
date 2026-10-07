from pathlib import Path

from mide.authorities import presentation_audio


def test_gs612_prepares_focus_from_same_final_order(monkeypatch):
    calls = {}

    def ordered(records):
        calls["input"] = list(records)
        return [{"symbol": "FNGR"}, {"symbol": "BIYA"}]

    def publish(records):
        calls["published"] = list(records)

    monkeypatch.setattr(
        presentation_audio,
        "final_enriched_opportunity_records",
        ordered,
    )
    monkeypatch.setattr(
        presentation_audio,
        "_publish_render_audio_focus",
        publish,
    )

    presentation_audio.prepare_completed_scan_audio_focus(
        [{"symbol": "BIYA"}, {"symbol": "FNGR"}]
    )

    assert calls["input"] == [{"symbol": "BIYA"}, {"symbol": "FNGR"}]
    assert calls["published"] == [{"symbol": "FNGR"}, {"symbol": "BIYA"}]


def test_gs621_visual_commit_precedes_audio_focus_and_semantic_delivery():
    source = Path("app.py").read_text(encoding="utf-8")

    prepare = source.index(
        "prepare_completed_scan_audio_focus(actionable_records)"
    )
    consume = source.index(
        "_audio_focus_records = current_render_audio_focus("
    )
    delivery = source.index(
        'play_alert("assets/alert.wav", alert_phrase',
        consume,
    )
    visual = source.index("with mission_plan_slot:")
    escalation = source.index("with escalation_engine_slot:", visual)

    assert visual < escalation < prepare < consume < delivery
    assert source.count("with mission_plan_slot:") == 1


def test_gs612_preserves_stale_scan_audio_guard():
    source = Path("app.py").read_text(encoding="utf-8")

    prepare = source.index(
        "prepare_completed_scan_audio_focus(actionable_records)"
    )
    stale_guard = source.index(
        "_audio_visible_scan_is_current = not (",
        prepare,
    )
    semantic_delivery = source.index(
        'play_alert("assets/alert.wav", alert_phrase',
        stale_guard,
    )

    assert prepare < stale_guard < semantic_delivery
    assert (
        "_audio_latest_process_scan.completed_at > completed_scan.completed_at"
        in source
    )
