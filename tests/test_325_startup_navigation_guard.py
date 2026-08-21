from pathlib import Path


APP = Path(__file__).resolve().parents[1] / "app.py"


def _app_source() -> str:
    return APP.read_text(encoding="utf-8")


def test_voice_preference_discovery_never_navigates_the_parent_page():
    """Startup preference discovery must not tear down the Streamlit session."""
    source = _app_source()

    assert "window.parent.location.replace" not in source
    assert "window.parent.history.replaceState" in source


def test_startup_url_update_preserves_existing_query_parameters():
    source = _app_source()

    assert "const params = new URLSearchParams(window.parent.location.search)" in source
    assert "`${{window.parent.location.pathname}}?${{params}}`" in source
