"""GS541: current-attention preload prevents render-time module-lock import."""

from pathlib import Path
import sys

from mide import gs541_current_attention_preload as gs541


ROOT = Path(__file__).resolve().parents[1]


def test_gs541_install_preloads_gs309_module():
    sys.modules.pop("mide.gs309_current_attention_mission", None)
    gs541.install()
    assert "mide.gs309_current_attention_mission" in sys.modules


def test_gs541_runs_from_hard_app_entry_before_other_warm_bindings():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    entry = app.index('log_startup("entering app.py")')
    preload_import = app.index(
        "from mide.gs541_current_attention_preload import install as _install_gs541_attention_preload"
    )
    preload_call = app.index("_install_gs541_attention_preload()")
    gs481_import = app.index(
        "from mide.gs481_live_evidence_hard_bind import install as _install_gs481_live_evidence"
    )

    assert entry < preload_import < preload_call < gs481_import


def test_gs541_is_import_only_and_has_no_trading_authority():
    source = (
        ROOT / "mide/gs541_current_attention_preload.py"
    ).read_text(encoding="utf-8")

    assert "gs309_current_attention_mission" in source
    forbidden = (
        "build_seed_symbols(",
        "current_attention_provenance(",
        "qualified_for_entry",
        "qualified_for_alert",
        "qualified_for_watch",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)


def test_gs376_still_uses_dynamic_gs309_public_provenance():
    source = (
        ROOT / "mide/gs376_reclaim_watch.py"
    ).read_text(encoding="utf-8")
    assert (
        "from .gs309_current_attention_mission import current_attention_provenance"
        in source
    )
