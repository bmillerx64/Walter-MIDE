from pathlib import Path


def test_auto_scan_timer_uses_session_preserving_streamlit_rerun():
    source = Path("app.py").read_text()

    assert "@st.fragment(run_every=" in source
    assert 'st.rerun(scope="app")' in source
    assert "root.location.reload()" not in source
