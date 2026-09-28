import ast
from pathlib import Path
import subprocess
import sys


def _startup_source() -> str:
    return Path("mide/startup.py").read_text(encoding="utf-8")


def test_gs587_pre_app_installers_are_not_module_import_side_effects():
    tree = ast.parse(_startup_source())
    forbidden = {
        "ensure_operator_card_order",
        "ensure_operator_visibility",
        "ensure_header_scan_truth",
        "ensure_operator_awareness",
        "ensure_reclaim_watch",
    }
    module_calls = {
        node.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        for node in [node.value]
        if isinstance(node.func, ast.Name)
    }
    assert forbidden.isdisjoint(module_calls)


def test_gs587_entering_app_boundary_preserves_pre_app_then_late_order():
    source = _startup_source()
    start = source.index('if component == "entering app.py":')
    end = source.index("\n\n\n@contextmanager", start)
    block = source[start:end]

    assert "ensure_pre_app_runtime_installers()" in block
    assert "ensure_late_runtime_installers()" in block
    assert block.index("ensure_pre_app_runtime_installers()") < block.index(
        "ensure_late_runtime_installers()"
    )


def test_gs587_clean_webull_import_exposes_completed_client_class():
    code = (
        "import mide.webull_live as live; "
        "assert hasattr(live, 'WebullOpenAPIClient'); "
        "assert hasattr(live.WebullOpenAPIClient, 'bars')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
