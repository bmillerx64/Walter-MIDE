import gzip
import json

from mide import ui
from mide.flight_recorder import FlightRecorder
from mide.memory import MemoryStore
from mide import gs310_unified_opportunity_state as unified
from mide import gs311_unified_voice as voice
from mide import gs314_state_consistency as consistency
from mide import gs363_operator_attention_hierarchy as hierarchy
from mide.gs364_live_operator_containment import (
    LARGE_EXPORT_BYTES,
    _gzip_export,
    bounded_latest_by_symbol,
)


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _attention_record(
    symbol,
    *,
    participation,
    expansion,
    vwap_distance=1.0,
    trend=True,
    volume_acceleration=0.5,
    dollar_flow_acceleration=0.5,
    reasons=None,
):
    return {
        "symbol": symbol,
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": vwap_distance,
        "supertrend_bullish": trend,
        "participation_surge_score": participation,
        "expansion_quality": expansion,
        "volume_acceleration": volume_acceleration,
        "dollar_flow_acceleration": dollar_flow_acceleration,
        "discovery_reasons": reasons or ["Webull native: day_gainers"],
    }


def test_latest_by_symbol_preserves_trailing_line_window_and_extends_append_only(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    _write(
        path,
        [
            {"symbol": "OLD", "value": 1},
            {"symbol": "KEEP", "value": 1},
            {"symbol": "A", "value": 1},
            {"symbol": "B", "value": 1},
            {"symbol": "A", "value": 2},
        ],
    )
    store = MemoryStore(path)

    first = bounded_latest_by_symbol(store, limit_lines=3)
    assert set(first) == {"A", "B"}
    assert first["A"]["value"] == 2

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"symbol": "C", "value": 1}) + "\n")
        handle.write(json.dumps({"symbol": "B", "value": 2}) + "\n")

    second = bounded_latest_by_symbol(store, limit_lines=3)
    assert set(second) == {"A", "B", "C"}
    assert second["B"]["value"] == 2


def test_installed_memory_store_uses_bounded_latest_path(tmp_path):
    path = tmp_path / "history.jsonl"
    _write(path, [{"symbol": "WALT", "value": 1}])
    store = MemoryStore(path)

    assert getattr(MemoryStore.latest_by_symbol, "_gs364_memory_containment", False)
    assert store.latest_by_symbol()["WALT"]["value"] == 1


def test_large_exports_are_gzip_compressed_without_changing_small_export_contract(tmp_path, monkeypatch):
    import mide.gs364_live_operator_containment as gs364

    small = tmp_path / "small.jsonl"
    small.write_bytes(b'{"symbol":"A"}\n')
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    assert _gzip_export(small) == small.read_bytes()

    large = tmp_path / "large.jsonl"
    payload = (b'{"symbol":"VIOT","evidence":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}\n' * 20)
    large.write_bytes(payload)
    compressed = _gzip_export(large)
    assert compressed[:2] == b"\x1f\x8b"
    assert gzip.decompress(compressed) == payload


def test_memory_and_flight_exports_keep_small_fixture_compatibility(tmp_path):
    history_path = tmp_path / "candidate.jsonl"
    flight_path = tmp_path / "flight.jsonl"
    history_path.write_bytes(b'{"symbol":"VIOT"}\n')
    flight_path.write_bytes(b'{"scan_id":"one"}\n')

    assert MemoryStore(history_path).export_bytes() == history_path.read_bytes()
    assert FlightRecorder(flight_path).export_bytes() == flight_path.read_bytes()


def test_plain_top_mover_needs_current_structure_or_flow_for_look_now():
    dgnx = _attention_record(
        "DGNX",
        participation=14,
        expansion=34,
        dollar_flow_acceleration=0.73,
    )
    gsun = _attention_record(
        "GSUN",
        participation=20,
        expansion=47,
        dollar_flow_acceleration=0.22,
    )
    ncpl = _attention_record(
        "NCPL",
        participation=45,
        expansion=39,
        trend=False,
        dollar_flow_acceleration=0.96,
    )

    assert unified.opportunity_state(dgnx)["state"] == unified.DEVELOPING
    assert unified.opportunity_state(gsun)["state"] == unified.DEVELOPING
    assert unified.opportunity_state(ncpl)["state"] == unified.DEVELOPING


def test_viot_like_top_mover_keeps_early_look_now_without_entry_thresholds():
    viot = _attention_record(
        "VIOT",
        participation=31.6,
        expansion=40,
        vwap_distance=1.41,
        trend=True,
        volume_acceleration=0.50,
        dollar_flow_acceleration=1.74,
    )

    view = unified.opportunity_state(viot)
    assert view["state"] == unified.LOOK_NOW
    assert viot["participation_surge_score"] < 72
    assert viot["expansion_quality"] < 58


def test_fresh_event_attention_remains_look_now_even_before_flow_confirmation():
    news = _attention_record(
        "NEWS",
        participation=10,
        expansion=20,
        trend=False,
        dollar_flow_acceleration=0.2,
        reasons=["FMP material news seed"],
    )

    assert unified.opportunity_state(news)["state"] == unified.LOOK_NOW


def test_every_trader_facing_state_binding_uses_gs364_calibration():
    assert getattr(unified.opportunity_state, "_gs364_look_now_precision", False)
    assert voice.opportunity_state is unified.opportunity_state
    assert consistency.opportunity_state is unified.opportunity_state
    assert hierarchy.opportunity_state is unified.opportunity_state


def test_exact_chime_layer_is_installed_after_gs363():
    assert getattr(ui.play_alert, "_gs363_operator_attention", False)
    assert getattr(ui.play_alert, "_gs364_exact_chimes", False)
    assert hierarchy.alert_chime_count("VIOT. Look Now.") == 2
    assert hierarchy.alert_chime_count("VIOT. Watch for Entry.") == 3
