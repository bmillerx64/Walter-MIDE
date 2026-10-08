from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs650_guard_generation_forces_warm_popup_upgrade():
    markup = alert_audio_health_markup()

    assert "const guardVersion = 'GS652';" in markup
    assert "guard.__walterAudioGuardVersion !== guardVersion" in markup
    assert "window.__walterAudioGuardVersion = 'GS652';" in markup


def test_gs650_upgrade_check_precedes_guard_reuse():
    markup = alert_audio_health_markup()

    condition = markup.index("guard.__walterAudioGuardVersion !== guardVersion")
    reuse = markup.index("typeof guard.__walterAudioGuard.refresh === 'function'")
    assert condition < reuse


def test_gs650_scope_lock_is_audio_guard_transport_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("const guardVersion = 'GS652';")
    end = source.index("const guardHealth = () => {", start)
    block = source[start:end]

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
    assert not any(token in block for token in forbidden)
