from mide.gs356_client_session_truth import (
    _watcher_html,
    header_with_session_truth,
)


def test_header_status_is_session_health_not_live_mode():
    markup = (
        "<div id='walter-status' class='control-stat-value control-live'>"
        "🟢 LIVE</div>"
    )
    rendered = header_with_session_truth(
        markup,
        {
            "text": "🟢 SESSION OK",
            "color": "#22c55e",
            "server_state": "READY",
            "scan_age_seconds": 42,
            "auto_scan": True,
            "reason": "",
        },
    )
    assert "🟢 SESSION OK" in rendered
    assert "🟢 LIVE" not in rendered
    assert "data-walter-scan-age='42'" in rendered
    assert "data-walter-auto='1'" in rendered
    assert "data-walter-server-state='READY'" in rendered


def test_browser_watcher_surfaces_streamlit_disconnect_and_stale_scan():
    html = _watcher_html("provider degraded")
    assert "CONNECTION LOST" in html
    assert "BROWSER OFFLINE" in html
    assert "SCAN STALE" in html
    assert "SESSION OK" in html
    assert "age > 150" in html
    assert "CONNECTING" in html
    assert "root.__walterSessionTruthInterval" in html
