from pathlib import Path


def test_live_architecture_runs_scanner_v2_after_velocity_before_expansion():
    source = Path("app.py").read_text(encoding="utf-8")

    velocity = source.index("analyzed = history.enrich_velocity(analyzed, previous=previous)")
    scanner = source.index("analyzed = scanner_module.apply_scanner_v2(", velocity)
    analyzed_map = source.index('analyzed_by_symbol = {item["symbol"]: item for item in analyzed}', scanner)
    expansion = source.index("def expansion(records):", analyzed_map)

    assert velocity < scanner < analyzed_map < expansion


def test_live_bridge_uses_runtime_scanner_module_not_stale_import_alias():
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'scanner_module = importlib.import_module("mide.scanner_v2")' in source
    assert "scanner_module.apply_scanner_v2(" in source


def test_live_bridge_preserves_architecture_membership_semantics():
    source = Path("app.py").read_text(encoding="utf-8")
    bridge = source[
        source.index("# GS530: the live Walter Architecture"):
        source.index('analyzed_by_symbol = {item["symbol"]: item for item in analyzed}')
    ]

    forbidden = (
        "if item.get("qualified_for_entry")",
        "if item.get("qualified_for_watch")",
        "return [",
        "filter(",
        "mission_rank",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in bridge for token in forbidden)


def test_gs529_shadow_can_now_reach_live_records():
    source = Path("app.py").read_text(encoding="utf-8")
    scanner = Path("mide/scanner_v2.py").read_text(encoding="utf-8")

    assert "scanner_module.apply_scanner_v2(" in source
    assert '"gs529_entry_ready_shadow": entry_ready_shadow' in scanner
    assert 'fields=("candidate_status", "qualified_for_entry", "trigger_diagnostics")' in source
