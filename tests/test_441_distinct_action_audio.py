from pathlib import Path

from mide import gs365_chime_semantic_classifier as semantics
from mide import gs367_browser_audio_broker as broker
from mide import gs441_distinct_action_audio as gs441


def test_gs441_overlays_unmistakable_action_patterns_only():
    markup = gs441.distinct_action_markup(broker.browser_broker_markup("scan-gs441", 2))

    assert "patterns['2'] = [[640,0.00],[1280,0.38]];" in markup
    assert "patterns['3'] = [[1568,0.00],[988,0.12],[1568,0.24]];" in markup
    assert "patterns['1'] =" not in markup
    assert "GS441: action-only signatures" in markup


def test_gs441_keeps_routine_heartbeat_acoustics_unchanged():
    markup = gs441.distinct_action_markup(broker.browser_broker_markup("scan-gs441-routine", 1))

    assert "tier === 3 ? 'square' : 'sine'" in markup
    assert ": (tier === 3 ? 0.52 : 0.24)" in markup
    assert ": (tier === 3 ? 0.10 : 0.13)" in markup
    assert ": (tier === 3 ? 0.12 : 0.145)" in markup
    assert broker.tone_pattern(1) == ((620, 0.0),)


def test_gs441_preserves_semantic_tier_truth():
    assert semantics.semantic_chime_count("ABCD. LOOK NOW.") == 2
    assert semantics.semantic_chime_count("ABCD. ENTRY READY.") == 3
    assert semantics.semantic_chime_count("ABCD. WATCH FOR ENTRY.") == 3
    assert semantics.semantic_chime_count("ABCD. ENTRY WINDOW OPEN.") == 3
    assert semantics.semantic_chime_count("ABCD. Not yet Entry Ready.") == 1

    # GS441 changes browser playback only; the historical public broker table remains
    # untouched so no semantic/routing contract is silently redefined.
    assert broker.tone_pattern(2) == ((900, 0.0), (1480, 0.28))
    assert broker.tone_pattern(3) == ((740, 0.0), (1047, 0.17), (1568, 0.34))


def test_gs441_applies_signature_after_final_broker_tier_selection():
    markup = gs441.distinct_action_markup(broker.browser_broker_markup("scan-gs441-order", 3))

    tier_selection = markup.index(
        "const tier = Math.max(1, Math.min(3, Number(broker.tier || 1)));"
    )
    final_envelope = markup.index("oscillator.type = tier === 2")

    assert tier_selection < final_envelope
    assert "broker.tier = Math.max(Number(broker.tier || 0), requestedTier);" in markup


def test_gs441_install_is_idempotent_and_chained_from_gs419():
    gs441.install()
    first = broker.browser_broker_markup
    gs441.install()

    assert broker.browser_broker_markup is first
    assert getattr(first, "_gs441_distinct_action_audio", False)

    gs419_source = Path("mide/gs419_completed_scan_heartbeat.py").read_text(encoding="utf-8")
    assert "from .gs441_distinct_action_audio import install as install_gs441" in gs419_source
    assert gs419_source.count("_install_gs441()") >= 2


def test_gs441_scope_lock_and_clean_runtime_marker():
    module = Path("mide/gs441_distinct_action_audio.py").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
        "candidate_status =",
        "request_scan(",
    )
    assert not any(token in module for token in forbidden)
    # Newer GS deployment markers may legitimately sit above GS441; preserve the
    # GS441 marker itself rather than pinning it forever to the first line.
    assert "# GS441 deployment marker:" in requirements
    assert "streamlit==1.62.0" in requirements
    assert "pandas==2.3.3" in requirements
    assert "numpy==2.5.1" in requirements
    assert "requests==2.34.2" in requirements
    assert "paho-mqtt==1.6.1" in requirements
    assert "webull-openapi-python-sdk==2.0.16" in requirements
