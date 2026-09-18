from pathlib import Path

from mide import gs365_chime_semantic_classifier as semantics
from mide import gs367_browser_audio_broker as broker
from mide import gs399_attention_audio_envelope as gs399
from mide import gs441_distinct_action_audio as gs441
from mide import gs504_distinct_attention_alarm as gs504


def _final_markup(tier: int) -> str:
    markup = broker.browser_broker_markup(f"scan-gs504-{tier}", tier)
    markup = gs399._attention_envelope_markup(markup)
    markup = gs441.distinct_action_markup(markup)
    return gs504.distinct_attention_markup(markup)


def test_tier2_is_harmonic_bell_not_another_bleep_sequence():
    markup = _final_markup(2)

    assert "GS504: categorical action audio" in markup
    assert "const gs504AttentionBell" in markup
    assert "strike(startBase, 523.25);" in markup
    assert "strike(startBase + 0.52, 783.99);" in markup
    assert "fundamental * 1.5" in markup
    assert "start + 0.62" in markup
    assert "if (tier === 2)" in markup
    assert "return true;" in markup


def test_tier3_is_sustained_siren_not_three_similar_bleeps():
    markup = _final_markup(3)

    assert "const gs504UrgentSiren" in markup
    assert "oscillator.type = 'sawtooth';" in markup
    assert "linearRampToValueAtTime" in markup
    assert "[980, 0.00], [1510, 0.16]" in markup
    assert "startBase + 1.10" in markup
    assert "if (tier === 3)" in markup


def test_tier1_still_falls_through_to_existing_routine_heartbeat():
    markup = _final_markup(1)

    # GS504 inserts no tier-1 alternate synthesis. Routine scan feedback remains
    # Walter's established single broker pattern.
    assert "if (tier === 1)" not in markup
    assert "const pattern = patterns[String(tier)] || patterns['1'];" in markup
    assert broker.tone_pattern(1) == ((620, 0.0),)


def test_semantic_tier_truth_is_unchanged():
    assert semantics.semantic_chime_count("ABCD. LOOK NOW.") == 2
    assert semantics.semantic_chime_count("ABCD. RUNNER DETECTED. LOOK NOW.") == 2
    assert semantics.semantic_chime_count("ABCD. WATCH FOR ENTRY.") == 3
    assert semantics.semantic_chime_count("ABCD. ENTRY READY.") == 3
    assert semantics.semantic_chime_count("ABCD. Not yet Entry Ready.") == 1


def test_gs504_runs_after_gs441_for_cold_and_warm_sessions():
    source = Path("mide/gs441_distinct_action_audio.py").read_text(encoding="utf-8")

    assert "from .gs504_distinct_attention_alarm import install as install_gs504" in source
    assert source.count("_install_gs504()") >= 2


def test_install_is_idempotent_and_preserves_prior_markers(monkeypatch):
    def baseline(scan_token: str, tier: int) -> str:
        return "<script>baseline</script>"

    baseline._gs441_distinct_action_audio = True
    monkeypatch.setattr(broker, "browser_broker_markup", baseline)

    gs504.install()
    first = broker.browser_broker_markup
    gs504.install()

    assert broker.browser_broker_markup is first
    assert getattr(first, "_gs504_distinct_attention_alarm", False)
    assert getattr(first, "_gs441_distinct_action_audio", False)


def test_scope_lock_is_audio_presentation_only():
    source = Path("mide/gs504_distinct_attention_alarm.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)


def test_deployment_marker_forces_clean_streamlit_audio_runtime():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "# GS504 deployment marker:" in requirements
