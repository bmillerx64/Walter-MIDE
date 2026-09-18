from pathlib import Path

from mide import gs496_static_session_backup as gs496


def test_generated_backup_href_is_origin_root_absolute(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    candidate.write_text('{"symbol":"A"}\n', encoding="utf-8")
    flight.write_text('{"scan":"one"}\n', encoding="utf-8")

    info = gs496.build_session_backup_archive(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        token="root-link",
    )

    assert info["href"].startswith("/app/static/")
    assert not info["href"].startswith("app/static/")
    assert "/~+/" not in info["href"]


def test_raw_html_anchor_uses_origin_root_path_not_current_streamlit_route():
    info = {
        "filename": "walter-session-backup-test.zip",
        "href": "/app/static/walter-session-backup-test.zip",
        "archive_bytes": 10,
        "source_bytes_total": 20,
    }
    markup = gs496.backup_link_markup(info)

    assert 'href="/app/static/walter-session-backup-test.zip"' in markup
    assert 'href="app/static/' not in markup


def test_streamlit_static_serving_remains_enabled():
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")
    assert "enableStaticServing = true" in config


def test_scope_lock_is_backup_delivery_only():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
