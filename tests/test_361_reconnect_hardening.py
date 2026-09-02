from mide import gs351_session_rerun_isolation as gs351
from mide import session_controls
from mide.gs356_client_session_truth import _watcher_html


def _idle_state():
    return {
        session_controls.SCAN_RUNNING_KEY: False,
        session_controls.SCAN_REQUESTED_KEY: False,
    }


def test_browser_connecting_detection_is_glyph_agnostic():
    html = _watcher_html()

    assert "body?.innerText" in html
    assert "CONNECTING\\b" in html
    assert "text === 'CONNECTING'" not in html
    assert "CONNECTION LOST" in html


def test_scheduled_app_rerun_waits_for_post_scan_render_window():
    state = _idle_state()
    state[gs351.LAST_SCAN_FINISHED_KEY] = 1_000.0

    assert (
        gs351.rerun_suppression_reason(
            state,
            now=200.0,
            epoch_now=1_005.0,
            protect_post_scan=True,
        )
        == "post-scan render cooldown"
    )


def test_post_scan_guard_does_not_block_default_reconnect_rerun():
    state = _idle_state()
    state[gs351.LAST_SCAN_FINISHED_KEY] = 1_000.0

    assert gs351.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1_005.0,
        protect_post_scan=False,
    ) is None


def test_scheduled_rerun_allowed_after_render_cooldown():
    state = _idle_state()
    state[gs351.LAST_SCAN_FINISHED_KEY] = 1_000.0

    assert gs351.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1_016.0,
        protect_post_scan=True,
    ) is None


def test_installed_finish_scan_records_render_boundary():
    state = {
        session_controls.SCAN_RUNNING_KEY: True,
        session_controls.SCAN_REQUESTED_KEY: True,
    }

    session_controls.finish_scan(state)

    assert state[session_controls.SCAN_RUNNING_KEY] is False
    assert state[session_controls.SCAN_REQUESTED_KEY] is False
    assert float(state[gs351.LAST_SCAN_FINISHED_KEY]) > 0
