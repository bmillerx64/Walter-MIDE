from pathlib import Path


def test_gs482_reasserts_gs481_from_streamlit_app_entry() -> None:
    app = Path("app.py").read_text(encoding="utf-8")
    entry = app.index('log_startup("entering app.py")')
    gs481_import = app.index(
        "from mide.gs481_live_evidence_hard_bind import install as _install_gs481_live_evidence"
    )
    gs481_call = app.index("_install_gs481_live_evidence()")
    memory_import = app.index("from mide.startup_memory import checkpoint as memory_checkpoint")

    assert entry < gs481_import < gs481_call < memory_import


def test_gs482_bridge_is_observability_only() -> None:
    app = Path("app.py").read_text(encoding="utf-8")
    start = app.index("# GS482:")
    end = app.index("from mide.startup_memory import checkpoint as memory_checkpoint")
    bridge = app[start:end]

    assert "gs481_live_evidence_hard_bind" in bridge
    assert "initialize_quotes" not in bridge
    assert "ensure_stream" not in bridge
    assert "qualified_for_entry" not in bridge
    assert "qualified_for_alert" not in bridge
