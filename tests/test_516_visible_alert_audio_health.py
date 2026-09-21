from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_visible_audio_health_reads_exact_gs367_parent_broker():
    markup = alert_audio_health_markup()
    assert "__walterGS367ChimeBroker" in markup
    assert "broker.audioContext.state === 'running'" in markup
    assert "walterVoiceArmed" in markup
    assert "sessionStorage" in markup


def test_visible_audio_health_exposes_stale_reload_state_and_direct_rearm():
    markup = alert_audio_health_markup()
    assert "AUDIO DISARMED AFTER RELOAD · RE-ARM" in markup
    assert "AUDIO NOT ARMED · RE-ARM" in markup
    assert "AUDIO READY · TEST CONFIRMED" in markup
    assert "Re-arm / test" in markup
    assert "button.addEventListener('click', rearm)" in markup
    assert "ctx.resume" in markup
    assert "createOscillator" in markup


def test_visible_audio_health_poll_detects_later_context_loss():
    markup = alert_audio_health_markup()
    assert "setInterval(refresh, 1000)" in markup
    assert "beforeunload" in markup


def test_rearm_preserves_voice_queue_and_tests_speech():
    markup = alert_audio_health_markup()
    assert "Walter alerts ready." in markup
    assert "synth.speak(utterance)" in markup
    assert "synth.cancel" not in markup


def test_scope_lock_is_alert_transport_presentation_only():
    source = Path("mide/gs516_visible_alert_audio_health.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)


def test_gs516_installs_after_gs515_discipline_layer():
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    assert chain.index("install_gs515()") < chain.index("install_gs516()")



def test_gs520_audio_health_is_anchored_in_sidebar_not_mission_placeholder():
    module_source = Path("mide/gs516_visible_alert_audio_health.py").read_text(
        encoding="utf-8"
    )
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "render_walter_mission_control" not in module_source
    assert "def render_sidebar_audio_health" in module_source
    assert "render_sidebar_audio_health(st)" in app_source
    assert app_source.index('"Alert voice"') < app_source.index(
        "render_sidebar_audio_health(st)"
    )


def test_gs520_preserves_single_child_mission_slot_contract():
    app_source = Path("app.py").read_text(encoding="utf-8")
    module_source = Path("mide/gs516_visible_alert_audio_health.py").read_text(
        encoding="utf-8"
    )

    assert "with mission_plan_slot:" in app_source
    assert "render_walter_mission_control(actionable_records)" in app_source
    assert "mission_plan_slot" not in module_source
