from pathlib import Path


def test_candidate_history_payload_is_materialized_after_scan_dispatch_boundary():
    app = Path("app.py").read_text(encoding="utf-8")

    placeholder = 'candidate_history_download_slot = st.empty()'
    dispatch = 'if mode.startswith("Live ") and should_scan and not st.session_state[STOP_REQUESTED_KEY]:'
    payload = 'data=get_store().export_bytes()'
    render = 'with candidate_history_download_slot:'

    assert placeholder in app
    assert dispatch in app
    assert render in app
    assert payload in app
    assert app.index(placeholder) < app.index(dispatch)
    assert app.index(dispatch) < app.index(render)
    assert app.index(render) < app.index(payload)


def test_candidate_history_download_ux_and_backup_contract_are_unchanged():
    app = Path("app.py").read_text(encoding="utf-8")

    start = app.index("with candidate_history_download_slot:")
    end = app.index("with flight_recorder_download_slot:", start)
    block = app[start:end]

    assert '"Download Candidate History"' in block
    assert 'file_name="candidate_history.jsonl"' in block
    assert 'mime="application/x-ndjson"' in block
    assert 'use_container_width=True' in block
    assert "data=get_store().export_bytes()" in block


def test_gs446_does_not_move_scan_authority():
    app = Path("app.py").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert requirements.startswith("# GS446 deployment marker:")
    assert "# GS445 deployment marker:" in requirements
    assert 'should_scan = st.session_state[SCAN_REQUESTED_KEY] or due' in app
    assert 'watchdog.run(' in app
