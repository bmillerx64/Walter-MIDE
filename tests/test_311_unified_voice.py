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


def test_no_fresh_prior_observation_means_no_repeated_voice_transition():
    assert unified_state_changes([_record()]) == []
    assert unified_alert_phrase([_record()]) == ""


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

    assert "<audio" not in markup
    assert "TEST. DEVELOPING." in markup
    assert "synth.speak(utterance)" in markup
