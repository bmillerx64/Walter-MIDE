from datetime import datetime, timezone
from types import SimpleNamespace

from mide import ui
from mide.gs367_browser_audio_broker import (
    BROKER_SETTLE_MS,
    broker_scan_token,
    browser_broker_markup,
    tone_pattern,
)


def _state(completed_at: datetime) -> dict:
    scan = SimpleNamespace(completed_at=completed_at)
    context = SimpleNamespace(
        completed_scan=scan,
        provider_instance=None,
        pipeline=None,
    )
    return {"scan_context": context}


def test_distinct_audio_tiers_have_unambiguous_patterns():
    assert len(tone_pattern(1)) == 1
    assert len(tone_pattern(2)) == 2
    assert len(tone_pattern(3)) == 3
    assert tone_pattern(1) != tone_pattern(2)
    assert tone_pattern(2) != tone_pattern(3)
    assert tone_pattern(3)[0][0] < tone_pattern(3)[-1][0]


def test_same_completed_scan_uses_same_browser_broker_token_for_distinct_phrases():
    state = _state(datetime(2026, 9, 2, 17, 15, 29, tzinfo=timezone.utc))

    first = broker_scan_token(state, "GELS. Coiling.")
    second = broker_scan_token(state, "VIOT. LOOK NOW.")

    assert first == second
    assert first.startswith("2026-09-02T17:15:29")


def test_no_completed_scan_keeps_non_scan_alerts_separate():
    state = {}
    first = broker_scan_token(state, "Voice changed to Alex.", "Alex")
    second = broker_scan_token(state, "Voice changed to Samantha.", "Samantha")

    assert first != second
    assert first.startswith("no-completed-scan|")


def test_browser_markup_aggregates_to_highest_tier_and_emits_once():
    markup = browser_broker_markup("scan-123", 2)

    assert "__walterGS367ChimeBroker" in markup
    assert "broker.tier = Math.max" in markup
    assert "broker.emittedToken === token" in markup
    assert "broker.emittedToken = token" in markup
    assert f"}}, {BROKER_SETTLE_MS});" in markup
    assert "AudioContext" in markup
    assert "createOscillator" in markup
    assert "<audio autoplay>" not in markup


def test_browser_markup_for_one_scan_can_upgrade_without_stacking_audio_components():
    routine = browser_broker_markup("scan-456", 1)
    look_now = browser_broker_markup("scan-456", 2)
    entry = browser_broker_markup("scan-456", 3)

    assert "const requestedTier = 1;" in routine
    assert "const requestedTier = 2;" in look_now
    assert "const requestedTier = 3;" in entry
    for markup in (routine, look_now, entry):
        assert "host[key]" in markup
        assert "clearTimeout" in markup
        assert "Math.max(Number(broker.tier || 0), requestedTier)" in markup


def test_gs367_is_final_installed_audio_layer():
    assert getattr(ui.play_alert, "_gs367_browser_audio_broker", False)
    assert getattr(ui.play_alert, "_gs366_rerun_alert_dedupe", False)
    assert getattr(ui.play_alert, "_gs365_chime_semantics", False)
