from mide.gs311_unified_voice import (
    _speech_component,
    unified_alert_phrase,
    unified_state_changes,
)


def _record(**overrides):
    record = {
        "symbol": "TEST",
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_surge_score": 80,
        "expansion_quality": 65,
        "volume_acceleration": 1.2,
        "discovery_reasons": ["Webull native: day_gainers"],
    }
    record.update(overrides)
    return record


def test_voice_transition_uses_same_unified_opportunity_state_as_display():
    previous = _record(
        vwap_relation="below",
        vwap_distance_pct=-0.5,
        supertrend_bullish=False,
        participation_surge_score=30,
        expansion_quality=30,
        volume_acceleration=0.7,
    )
    current = _record(opportunity_pulse_previous=previous)

    changes = unified_state_changes([current])

    assert changes == [
        {"symbol": "TEST", "from": "LOOK NOW", "to": "WATCH FOR ENTRY"}
    ]
    assert "TEST. WATCH FOR ENTRY." in unified_alert_phrase([current])


def test_proven_first_actionable_attention_is_spoken_once_on_first_print():
    current = _record(
        discovery_history=[{"scan": 7, "event": "first_seen"}],
        discovery_last_seen_scan=7,
    )

    changes = unified_state_changes([current])

    assert changes == [
        {
            "symbol": "TEST",
            "from": "NEW",
            "to": "WATCH FOR ENTRY",
            "event": "first_actionable_attention",
        }
    ]
    assert "TEST. WATCH FOR ENTRY." in unified_alert_phrase([current])


def test_no_fresh_prior_observation_means_no_repeated_voice_transition():
    assert unified_state_changes([_record()]) == []
    assert unified_alert_phrase([_record()]) == ""


def test_compacted_record_without_explicit_first_seen_evidence_does_not_realert():
    current = _record(
        discovery_first_seen_at="2026-08-21T13:00:00+00:00",
        discovery_last_seen_at="2026-08-21T13:05:00+00:00",
    )

    assert unified_state_changes([current]) == []
    assert unified_alert_phrase([current]) == ""


def test_speech_component_targets_parent_browser_with_iframe_fallback():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert "window.parent" in markup
    assert "speechWindow = window" in markup
    assert "speechSynthesis" in markup
    assert "SpeechSynthesisUtterance" in markup
    assert "TEST. LOOK NOW." in markup
    assert "Samantha" in markup


def test_missing_sound_file_does_not_suppress_spoken_phrase():
    markup = _speech_component("definitely-not-present.wav", "TEST. DEVELOPING.")

    assert "<audio autoplay>" not in markup
    assert "TEST. DEVELOPING." in markup
    assert "synth.speak(utterance)" in markup


def test_voice_transport_resumes_stuck_browser_synth_before_speaking():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    assert "synth.paused" in markup
    assert "synth.resume()" in markup
    assert "synth.cancel()" in markup
    assert markup.index("synth.resume()") < markup.index("synth.speak(utterance)")


def test_voice_transport_waits_for_cancel_to_settle_before_speaking():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    assert "speechWindow.setTimeout(() =>" in markup
    assert "}, 75);" in markup
    assert markup.index("synth.cancel()") < markup.index("speechWindow.setTimeout(() =>")
    assert markup.index("speechWindow.setTimeout(() =>") < markup.index("synth.speak(utterance)")


def test_voice_transport_retains_async_fallback_after_delayed_primary_speak():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    delayed_speak = markup.index("synth.speak(utterance)")
    primary_fallback = markup.index("parent synth failed; using frame fallback")
    frame_speak = markup.index("window.speechSynthesis.speak(utterance)")
    assert delayed_speak < primary_fallback < frame_speak
    assert "synth setup failed; using frame fallback" in markup


def test_voice_transport_retains_utterance_until_browser_finishes():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    assert "speechWindow.__walterActiveUtterance = utterance" in markup
    assert "utterance.onend = () => release('ended')" in markup
    assert "utterance.onerror = (event) =>" in markup
    assert "release('error'" in markup


def test_voice_transport_does_not_require_preferred_voice_to_exist():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert "resolveVoice" in markup
    assert "attempts >= 12" in markup
    assert "speakInitialOnce();" in markup


def test_voice_transport_exposes_browser_lifecycle_statuses():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert 'id="walter-voice-status"' in markup
    assert "Voice: initializing" in markup
    assert "setStatus('requested'" in markup
    assert "setStatus('speaking'" in markup
    assert "release('ended')" in markup
    assert "release('error'" in markup
    assert "setStatus('unavailable'" in markup


def test_voice_transport_replay_is_manual_and_does_not_create_an_alert_event():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert 'id="walter-voice-test"' in markup
    assert "Replay test" in markup
    assert "replayNode.addEventListener('click'" in markup
    assert "speak('manual replay')" in markup
    assert "speak('Walter alert')" in markup


def test_voice_transport_reports_requested_and_actual_voice():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert "actualVoice" in markup
    assert "preferred" in markup
    assert "selectedVoice ? selectedVoice.name" in markup
    assert "System Default" in markup


def test_voice_transport_status_is_accessible_and_visible():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    assert 'role="status"' in markup
    assert 'aria-live="polite"' in markup
    assert "height:38px" in markup
