from mide.gs311_unified_voice import _speech_component
from mide.gs318_voice_observability import record_voice_request, voice_request_snapshot


def test_voice_request_observability_records_transport_handoff_without_trading_state():
    session_state = {}

    first = record_voice_request(
        session_state,
        phrase="TEST. WATCH FOR ENTRY.",
        voice_name="Samantha",
    )
    second = record_voice_request(
        session_state,
        phrase="NEXT. LOOK NOW.",
    )

    snapshot = voice_request_snapshot(session_state)

    assert first["count"] == 1
    assert second["count"] == 2
    assert snapshot["count"] == 2
    assert snapshot["phrase"] == "NEXT. LOOK NOW."
    assert snapshot["voice"] == ""
    assert snapshot["requested_at"]
    assert set(session_state) == {
        "_walter_voice_request_count",
        "_walter_voice_last_requested_phrase",
        "_walter_voice_last_requested_voice",
        "_walter_voice_last_requested_at",
    }


def test_voice_request_snapshot_is_read_only():
    session_state = {
        "_walter_voice_request_count": 3,
        "_walter_voice_last_requested_phrase": "ABC. LOOK NOW.",
        "_walter_voice_last_requested_voice": "Samantha",
        "_walter_voice_last_requested_at": "2026-08-21T12:00:00+00:00",
    }
    before = dict(session_state)

    snapshot = voice_request_snapshot(session_state)

    assert snapshot["count"] == 3
    assert snapshot["phrase"] == "ABC. LOOK NOW."
    assert session_state == before


def test_browser_voice_component_exposes_delivery_lifecycle_diagnostics():
    markup = _speech_component(
        "definitely-not-present.wav",
        "TEST. WATCH FOR ENTRY.",
        "Samantha",
    )

    assert "__walterVoiceTransport" in markup
    assert "status: 'requested'" in markup
    assert "status: 'speaking'" in markup
    assert "release('ended')" in markup
    assert "release('error')" in markup
    assert "[Walter voice] request accepted by component" in markup
    assert "[Walter voice] speaking" in markup
    assert "[Walter voice] synthesis error" in markup
