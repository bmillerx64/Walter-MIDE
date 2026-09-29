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
    assert "AUDIO READY · TEST PLAYING" in markup
    assert "Re-arm / test" in markup
    assert "button.addEventListener('click', () => {" in markup
    assert "testVoice();" in markup
    assert "rearm();" in markup
    assert "ctx.resume" in markup
    assert "createOscillator" in markup


def test_visible_audio_health_poll_detects_later_context_loss():
    markup = alert_audio_health_markup()
    assert "setInterval(refresh, 1000)" in markup
    assert "beforeunload" in markup


def test_gs596_explicit_rearm_speaks_synchronously_when_queue_is_idle():
    markup = alert_audio_health_markup()
    listener = markup.index("button.addEventListener('click', () => {")
    test_start = markup.index("const testVoice = () => {")
    rearm_start = markup.index("const rearm = () => {", test_start)
    block = markup[test_start:rearm_start]

    assert "Walter alerts ready." in block
    assert "const queueBusy = Boolean(" in block
    assert "synth.pending || synth.speaking || synth.paused" in block
    assert "queue cleared · click Re-arm / test again" in block
    assert "speakFresh(0);" in block
    assert "window.setTimeout(() => speakFresh(0), 300);" not in block
    assert "window.setTimeout(() => speakFresh(attempt + 1), 450);" not in block
    assert "GS596 parent-sync re-arm" in block
    assert markup.index("testVoice();", listener) < markup.index("rearm();", listener)



def test_gs596_voice_test_prefers_parent_engine_inside_direct_activation():
    markup = alert_audio_health_markup()
    listener = markup.index("button.addEventListener('click', () => {")
    voice_call = markup.index("testVoice();", listener)
    rearm_call = markup.index("rearm();", listener)
    rearm_start = markup.index("const rearm = () => {")
    play_start = markup.index("const play = () => {", rearm_start)
    play_end = markup.index("          };", play_start)

    assert listener < voice_call < rearm_call
    assert "testVoice();" not in markup[play_start:play_end]
    assert "resumed.then(play)" in markup[rearm_start:listener]
    assert "GS596: GS595 proved frame-local synchronous speech still reaches" in markup
    assert "const parentSpeechAvailable = Boolean(" in markup
    assert "? root.speechSynthesis" in markup
    assert "? root.SpeechSynthesisUtterance" in markup
    assert "const speechScope = parentSpeechAvailable ? 'parent' : 'frame';" in markup


def test_gs596_audio_health_reports_scope_and_outcome_without_timer_retry():
    markup = alert_audio_health_markup()
    assert "BELL READY · VOICE RESETTING" in markup
    assert "BELL READY · VOICE REQUESTED" in markup
    assert "AUDIO + VOICE READY" in markup
    assert "BELL READY · VOICE BLOCKED" in markup
    assert "utterance.onstart" in markup
    assert "utterance.onend" in markup
    assert "utterance.onerror" in markup
    assert "no start callback" in markup
    assert "click Re-arm / test again" in markup
    assert "window.setTimeout(() => speakFresh(attempt + 1), 450);" not in markup
    assert "GS596 parent-sync re-arm" in markup
    assert "scope=${scope}" in markup


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


def test_gs596_audio_health_keeps_bell_and_expands_visible_diagnostics():
    markup = alert_audio_health_markup()
    assert "grid-template-columns:minmax(0,1fr) auto" in markup
    assert "overflow-wrap:anywhere" in markup
    assert "frequency * 1.5" in markup
    assert "exponentialRampToValueAtTime(0.30" in markup
    assert "strike(base, 523.25)" in markup
    assert "strike(base + 0.42, 783.99)" in markup
    assert "AUDIO READY · TEST PLAYING" in markup


def test_gs597_voice_diagnostic_scope_is_explicit_not_free_variable():
    markup = alert_audio_health_markup()
    assert "const voiceEngineDetail = (synth, scope = 'unknown') => {" in markup
    assert "scope=${scope}" in markup
    assert "scope=${speechScope}" not in markup
    assert markup.count("voiceEngineDetail(synth, speechScope)") >= 5
