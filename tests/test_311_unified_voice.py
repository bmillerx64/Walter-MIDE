from mide.gs311_unified_voice import (
    _compact_guard_phrase,
    _speech_component,
    _synthesize_phrase_wav,
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
    assert unified_state_changes([current]) == [
        {"symbol": "TEST", "from": "DEVELOPING", "to": "WATCH FOR ENTRY"}
    ]
    assert "TEST. WATCH FOR ENTRY." in unified_alert_phrase([current])


def test_proven_first_actionable_attention_is_spoken_once_on_first_print():
    current = _record(
        discovery_history=[{"scan": 7, "event": "first_seen"}],
        discovery_last_seen_scan=7,
    )
    assert unified_state_changes([current]) == [
        {
            "symbol": "TEST",
            "from": "NEW",
            "to": "WATCH FOR ENTRY",
            "event": "first_actionable_attention",
        }
    ]


def test_no_fresh_prior_observation_means_no_repeated_voice_transition():
    assert unified_state_changes([_record()]) == []
    assert unified_alert_phrase([_record()]) == ""


def test_gs654_compacts_operator_voice_to_clear_ticker_and_primary_state():
    assert _compact_guard_phrase("JZ. LOOK NOW. 1 minute bullish. 3 minute building.") == "Ticker J. Z. look now."
    assert _compact_guard_phrase("OLB. IGNITION. VWAP above.") == "Ticker O. L. B. ignition."
    assert _compact_guard_phrase("TEST. WATCH FOR ENTRY.") == "Ticker T. E. S. T. watch for entry."
    assert _compact_guard_phrase("SOAR. DEVELOPING.") == "Ticker S. O. A. R. developing."


def test_gs653_missing_espeak_is_truthful(monkeypatch):
    _synthesize_phrase_wav.cache_clear()
    monkeypatch.setattr("mide.gs311_unified_voice.shutil.which", lambda _: None)
    assert _synthesize_phrase_wav("T E S T. alert.") == ""
    _synthesize_phrase_wav.cache_clear()


def test_gs653_voice_component_routes_only_to_persistent_web_audio_guard():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")
    assert "walterAudioGuardHeartbeat" in markup
    assert "walterAudioGuardVersion" in markup
    assert "walterAudioGuardVoiceReady" in markup
    assert "walter-audio-guard-v1" in markup
    assert "kind: 'voice_wav'" in markup
    assert "audioBase64" in markup
    assert "audioKey" in markup
    assert "GS662" in markup
    assert "Open / test Audio Guard" in markup


def test_gs653_voice_component_has_no_browser_speech_synthesis_fallback():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")
    assert "speechSynthesis" not in markup
    assert "SpeechSynthesisUtterance" not in markup
    assert "synth.cancel" not in markup
    assert "synth.speak" not in markup
    assert "sessionStorage" not in markup


def test_gs653_named_browser_voice_is_not_part_of_transport_anymore():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")
    assert "Samantha" not in markup
    assert "System Default" not in markup


def test_voice_transport_status_is_accessible_and_visible():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")
    assert 'role="status"' in markup
    assert 'aria-live="polite"' in markup
    assert "height:38px" in markup
