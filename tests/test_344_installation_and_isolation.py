import ast
from pathlib import Path

from mide import ui


def test_gs344_installed_after_existing_operator_cues():
    assert getattr(ui.render_walter_mission_control, "_gs344_emergence_convergence_engine", False)
    recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(recommendation):
        assert getattr(recommendation, "_gs344_emergence_convergence_engine", False)


def test_gs344_does_not_import_execution_scanner_or_order_modules():
    source = Path("mide/gs344_emergence_convergence_engine.py").read_text()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden = ("alpaca", "execution", "orders", "scanner", "architecture")
    for module_name in imported:
        lowered = module_name.lower()
        assert not any(fragment in lowered for fragment in forbidden)


def test_gs344_source_preserves_stronger_operator_states():
    source = Path("mide/gs344_emergence_convergence_engine.py").read_text()
    for token in ("MOMENTUM IGNITING", "LOOK NOW", "WATCH FOR ENTRY", "ENTRY", "CHASE", "RESET REQUIRED"):
        assert token in source
