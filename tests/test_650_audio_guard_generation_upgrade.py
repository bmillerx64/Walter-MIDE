from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs653_guard_generation_forces_warm_popup_upgrade():
    markup = alert_audio_health_markup()
    assert "const VERSION = 'GS653';" in markup
    assert "guard.__walterAudioGuardVersion !== VERSION" in markup
    assert "guard.__walterAudioGuardVersion = VERSION;" in markup
    assert "walterAudioGuardVersion" in markup


def test_gs653_upgrade_check_precedes_guard_reuse():
    markup = alert_audio_health_markup()
    condition = markup.index("guard.__walterAudioGuardVersion !== VERSION")
    reuse = markup.index("typeof guard.__walterAudioGuard.refresh === 'function'")
    assert condition < reuse


def test_gs653_scope_lock_is_audio_guard_transport_only():
    source = Path("mide/audio_guard_v2.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "candidate_status",
        "participation_score",
        "expansion_score",
        "request_scan(",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in source for token in forbidden)
