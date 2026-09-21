from pathlib import Path

from mide import gs496_static_session_backup as gs496


def test_prepared_backup_uses_native_deferred_bytes_not_static_anchor():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")

    assert "st.download_button(" in source
    assert "data=materialize_prepared_archive" in source
    assert 'mime="application/zip"' in source
    assert 'on_click="ignore"' in source
    assert 'return archive_path.read_bytes()' in source

    render_start = source.index("def _render_backup_controls")
    render_end = source.index("def render_session_backup_controls", render_start)
    render = source[render_start:render_end]
    assert "st.markdown(backup_link_markup" not in render


def test_download_callable_materializes_bytes_only_after_click():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
    block_start = source.index("def materialize_prepared_archive")
    block_end = source.index("st.download_button(", block_start)
    block = source[block_start:block_end]

    assert '.read_bytes()' in block
    assert '.open("rb")' not in block
    # The bytes allocation stays inside the deferred callable, never at render time.
    render_start = source.index("def _render_backup_controls")
    render_end = source.index("def render_session_backup_controls", render_start)
    render = source[render_start:render_end]
    before_callable = render.split("def materialize_prepared_archive", 1)[0]
    assert ".read_bytes()" not in before_callable


def test_native_download_remains_inside_self_refreshing_fragment():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")

    assert "@fragment(run_every=JOB_POLL_SECONDS)" in source
    assert "materialize_prepared_archive" in source


def test_gs509_does_not_depend_on_runtime_static_route_for_delivery():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
    render_start = source.index("def _render_backup_controls")
    render_end = source.index("def render_session_backup_controls", render_start)
    render = source[render_start:render_end]

    assert 'href' not in render
    assert "backup_link_markup(" not in render


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
