from pathlib import Path


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs601_observer_arms_audio_only_when_completed_scan_is_still_current():
    source = _app_source()
    start = source.index("def adopt_newer_process_scan() -> None:")
    end = source.index(
        "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))",
        start,
    )
    observer = source[start:end]

    assert "audio_snapshot" in observer
    assert "audio_snapshot.last_started_at > observed.completed_at" in observer
    assert "skipped stale completed scan before repaint" in observer
    marker = 'st.session_state["_walter_process_scan_audio_pending_token"] = ('
    assert marker in observer
    assert observer.index("newer_scan_started = bool(") < observer.index(marker)
    assert observer.index(marker) < observer.index('st.rerun(scope="app")')


def test_gs601_registers_process_audio_after_complete_dashboard_render():
    source = _app_source()
    semantic = source.index(
        'play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())'
    )
    debug_view = source.index('if active_tab == "Webull Debug":')
    marker = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render"
    )
    handoff = source[marker:]

    # GS612: semantic voice follows the completed surface at the end of the
    # heavy render, while GS601's process heartbeat remains the final handoff.
    assert debug_view < semantic < marker
    assert "_process_audio_snapshot = _gs585.snapshot()" in handoff
    assert "_process_audio_pending == _process_audio_current" in handoff
    assert (
        "_process_audio_snapshot.last_started_at > completed_scan.completed_at"
        in handoff
    )
    assert 'from mide.gs419_completed_scan_heartbeat import heartbeat_markup' in handoff
    assert "heartbeat_markup(st.session_state)" in handoff
    assert "st.components.v1.html(" in handoff
    assert "[WALTER AUDIO] process scan browser registration" in handoff


def test_gs601_stale_process_audio_token_is_always_consumed():
    source = _app_source()
    marker = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render"
    )
    handoff = source[marker:]

    assert "[WALTER AUDIO] dropped stale process scan token" in handoff
    pop = 'st.session_state.pop("_walter_process_scan_audio_pending_token", None)'
    assert pop in handoff
    assert handoff.rindex(pop) > handoff.index("_process_audio_matches_visible")


def test_gs601_audio_handoff_is_presentation_only():
    source = _app_source()
    marker = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render"
    )
    handoff = source[marker:]

    forbidden = (
        "participation_score",
        "expansion_score",
        "qualified_for_entry",
        "qualified_for_alert",
        "mission_rank",
        "SuperTrend",
        "VWAP",
        "place_order(",
        "submit_order(",
        "SCAN_REQUESTED_KEY",
    )
    assert not any(token in handoff for token in forbidden)
