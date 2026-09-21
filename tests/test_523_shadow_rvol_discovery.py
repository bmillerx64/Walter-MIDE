from pathlib import Path

from mide.flight_recorder import FlightRecorder


def test_shadow_discovery_is_scan_level_forensic_evidence_only(tmp_path):
    recorder = FlightRecorder(tmp_path / "flight.jsonl")
    class Settings:
        min_price = 0.05
        max_price = 5.0
        min_pct_change = 3.0
        min_day_volume = 100000
        max_free_float = 20_000_000

    shadow = {
        "relative_volume_page2": {
            "status": "PASS",
            "symbols": ["AUUD"],
            "rows": [{"symbol": "AUUD", "rank": 27}],
            "admitted_to_discovery": False,
        }
    }
    scan = recorder.record_scan(
        seeds=[],
        discovery_reasons={},
        snapshots={},
        candidates=[],
        analyzed=[],
        records=[],
        settings=Settings(),
        shadow_discovery=shadow,
    )
    assert scan["shadow_discovery"] == shadow
    assert scan["funnel"]["Sampled"] == 0


def test_gs523_does_not_add_shadow_rows_to_live_symbols():
    source = Path("mide/gs395_earlier_discovery_breadth.py").read_text(encoding="utf-8")
    block = source[source.index("# GS523: observe"):source.index('output["supplemental_breadth"] = {')]
    assert 'ordered.append' not in block
    assert 'by_symbol[' not in block
    assert 'admitted.append' not in block
    assert '"admitted_to_discovery": False' in block


def test_app_persists_shadow_discovery_but_never_uses_it_as_seed_input():
    source = Path("app.py").read_text(encoding="utf-8")
    assert 'shadow_discovery=dict(' in source
    assert 'client.diagnostics.get("webull_native_discovery")' in source
