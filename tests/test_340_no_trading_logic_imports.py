import ast
from pathlib import Path


def test_gs340_does_not_import_execution_or_scanner_modules():
    source = Path("mide/gs340_high_liquidity_trend_watch.py").read_text()
    tree = ast.parse(source)

    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden_fragments = ("alpaca", "execution", "orders", "scanner", "architecture")
    for module_name in imported:
        lowered = module_name.lower()
        assert not any(fragment in lowered for fragment in forbidden_fragments)
