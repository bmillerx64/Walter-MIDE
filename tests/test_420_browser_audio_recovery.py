from pathlib import Path

from mide.gs352_persistent_alert_arm import alert_arm_markup
from mide.gs367_browser_audio_broker import browser_broker_markup


def test_gs420_does_not_burn_scan_token_before_audio_is_running():
    markup = browser_broker_markup("scan-gs420", 2)

    running_guard = "if (!context || context.state !== 'running') return false;"
    emitted_assignment = "broker.emittedToken = token;"

    assert running_guard in markup
    assert emitted_assignment in markup
    assert markup.index(running_guard) < markup.index(emitted_assignment)
    assert "only claim delivery after a running context accepted the pattern" in markup


def test_gs420_retains_pending_tier_and_retries_after_user_activation():
    markup = browser_broker_markup("scan-gs420-pending", 3)

    assert "pendingToken" in markup
    assert "pendingTier" in markup
    assert "pendingEmit" in markup
    assert "bindUnlockRetry" in markup
    assert "host.addEventListener('pointerdown', unlock, true)" in markup
    assert "host.addEventListener('keydown', unlock, true)" in markup
    assert "resumed.then" in markup


def test_gs420_alert_arm_primes_same_parent_broker_context():
    markup = alert_arm_markup()

    assert "__walterGS367ChimeBroker" in markup
    assert "root.AudioContext || root.webkitAudioContext" in markup
    assert "broker.audioContext = ctx" in markup
    assert "ctx.state === 'running'" in markup
    assert "Re-test after reload" in markup


def test_gs420_changes_only_browser_alert_transport_contract():
    broker_source = Path("mide/gs367_browser_audio_broker.py").read_text(encoding="utf-8")
    arm_source = Path("mide/gs352_persistent_alert_arm.py").read_text(encoding="utf-8")
    source = broker_source + arm_source

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "candidate_status =",
        "opportunity_state =",
    )
    assert not any(token in source for token in forbidden)
