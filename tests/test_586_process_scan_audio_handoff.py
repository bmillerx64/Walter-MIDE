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

    assert "latest_process_scan = process_live_scan_snapshot()" in observer
    assert "latest_process_scan.completed_at > observed.completed_at" in observer
    assert "skipped superseded completed scan before repaint" in observer
    marker = 'st.session_state["_walter_process_scan_audio_pending_token"] = ('
    assert marker in observer
    assert observer.index("newer_completed_scan = bool(") < observer.index(marker)
    assert observer.index(marker) < observer.index('st.rerun(scope="app")')


def test_gs621_registers_process_audio_after_critical_surface_before_heavy_dashboard():
    source = _app_source()
    semantic = source.index(
        'play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())'
    )
    mission = source.index("with mission_plan_slot:")
    marker = source.index(
        "# GS621: register routine completed-scan browser audio immediately"
    )
    radar = source.index("tab_names = [")
    handoff = source[marker:radar]

    assert mission < semantic < marker < radar
    assert "_process_audio_latest_completed = process_live_scan_snapshot()" in handoff
    assert "_process_audio_pending == _process_audio_current" in handoff
    assert (
        "_process_audio_latest_completed.completed_at > completed_scan.completed_at"
        in handoff
    )
    assert 'from mide.gs419_completed_scan_heartbeat import heartbeat_markup' in handoff
    assert "heartbeat_markup(st.session_state)" in handoff
    assert "st.components.v1.html(" in handoff
    assert "[WALTER AUDIO] process scan browser registration" in handoff


def test_gs601_stale_process_audio_token_is_always_consumed():
    source = _app_source()
    marker = source.index(
        "# GS621: register routine completed-scan browser audio immediately"
    )
    boundary = source.index("tab_names = [", marker)
    handoff = source[marker:boundary]

    assert "[WALTER AUDIO] dropped superseded process scan token" in handoff
    pop = 'st.session_state.pop("_walter_process_scan_audio_pending_token", None)'
    assert pop in handoff
    assert handoff.rindex(pop) > handoff.index("_process_audio_matches_visible")


def test_gs601_audio_handoff_is_presentation_only():
    source = _app_source()
    marker = source.index(
        "# GS621: register routine completed-scan browser audio immediately"
    )
    boundary = source.index("tab_names = [", marker)
    handoff = source[marker:boundary]

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
