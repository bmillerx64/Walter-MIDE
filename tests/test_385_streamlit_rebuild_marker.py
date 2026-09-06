from pathlib import Path


def test_gs385_streamlit_rebuild_marker_preserves_pinned_dependencies():
    requirements = Path("requirements.txt").read_text()

    assert "GS385 deployment marker" in requirements
    assert "streamlit==1.62.0" in requirements
    assert "pandas==2.3.3" in requirements
    assert "numpy==2.5.1" in requirements
    assert "requests==2.34.2" in requirements
    assert "paho-mqtt==1.6.1" in requirements
    assert "webull-openapi-python-sdk==2.0.16" in requirements
