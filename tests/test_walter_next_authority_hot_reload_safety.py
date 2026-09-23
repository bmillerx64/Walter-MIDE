"""Phase 10: authority facades must not freeze replaceable legacy callables."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _imported_names(path: str, module: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def test_discovery_news_does_not_freeze_replaceable_functions():
    assert not (
        _imported_names("mide/authorities/discovery_news.py", "mide.discovery")
        & {
            "build_seed_symbols",
            "is_valid_us_symbol",
            "prefilter_snapshots",
            "snapshot_identity_records",
        }
    )
    assert "index_news" not in _imported_names(
        "mide/authorities/discovery_news.py", "mide.news"
    )
    assert not (
        _imported_names("mide/authorities/discovery_news.py", "mide.news_provider")
        & {"symbol_news_evidence", "ticker_inspection"}
    )


def test_entry_authority_does_not_freeze_scanner_or_shadow_functions():
    assert not (
        _imported_names("mide/authorities/entry_authority.py", "mide.scanner_v2")
        & {
            "qualified_for_alert",
            "qualified_for_entry",
            "qualified_for_watch",
            "trigger_diagnostics",
        }
    )
    assert "retest_entry_shadow" not in _imported_names(
        "mide/authorities/entry_authority.py",
        "mide.gs532_retest_entry_shadow",
    )


def test_replay_validation_keeps_classes_stable_but_functions_dynamic():
    flight_imports = _imported_names(
        "mide/authorities/replay_validation.py",
        "mide.flight_recorder",
    )
    assert "FlightRecorder" in flight_imports
    assert "prefilter_decision" not in flight_imports
    assert "scan_integrity_report" not in _imported_names(
        "mide/authorities/replay_validation.py",
        "mide.data_integrity",
    )
