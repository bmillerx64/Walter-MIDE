from pathlib import Path


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs586_observer_marks_exact_adopted_process_scan_for_audio():
    source = _app_source()
    start = source.index("def adopt_newer_process_scan() -> None:")
    end = source.index(
        "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))",
        start,
    )
    observer = source[start:end]

    marker = 'st.session_state["_walter_process_scan_audio_pending_token"] = ('
    assert marker in observer
    assert "observed.completed_at.isoformat()" in observer
    assert observer.index(marker) < observer.index('st.rerun(scope="app")')


def test_gs586_registers_heartbeat_after_semantic_alert_selection():
    source = _app_source()
    semantic = source.index(
        'play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())'
    )
    marker = source.index("# GS586: process-owned scans finish outside Streamlit.")
    tabs = source.index("tab_names = [", marker)
    handoff = source[marker:tabs]

    assert semantic < marker
    assert 'from mide.gs419_completed_scan_heartbeat import heartbeat_markup' in handoff
    assert "heartbeat_markup(st.session_state)" in handoff
    assert "st.components.v1.html(" in handoff
    assert (
        'st.session_state.pop("_walter_process_scan_audio_pending_token", None)'
        in handoff
    )
    assert "[WALTER AUDIO] process scan browser registration" in handoff


def test_gs586_audio_handoff_is_presentation_only():
    source = _app_source()
    marker = source.index("# GS586: process-owned scans finish outside Streamlit.")
    end = source.index("tab_names = [", marker)
    handoff = source[marker:end]

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
