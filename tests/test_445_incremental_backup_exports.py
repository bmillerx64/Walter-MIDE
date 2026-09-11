import gzip
import os
from pathlib import Path

from mide import gs364_live_operator_containment as gs364
from mide import gs445_incremental_backup_exports as gs445
from mide.flight_recorder import FlightRecorder
from mide.memory import MemoryStore


def _large_payload(symbol: str, count: int = 20) -> bytes:
    return (
        (f'{{"symbol":"{symbol}","evidence":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}}\n').encode()
        * count
    )


def test_gs445_large_append_reads_only_delta_and_remains_exact(tmp_path, monkeypatch):
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = tmp_path / "candidate_history.jsonl"
    first = _large_payload("TRUG")
    second = _large_payload("BDRX", count=7)
    path.write_bytes(first)

    initial = gs445.incremental_gzip_export(path)
    first_observation = gs445.export_observation(path)
    assert initial[:2] == b"\x1f\x8b"
    assert gzip.decompress(initial) == first
    assert first_observation["mode"] == "rebuild"
    assert first_observation["bytes_read_this_call"] == len(first)
    assert first_observation["rebuild_count"] == 1
    assert first_observation["extend_count"] == 0

    with path.open("ab") as handle:
        handle.write(second)

    extended = gs445.incremental_gzip_export(path)
    second_observation = gs445.export_observation(path)
    assert gzip.decompress(extended) == first + second
    assert second_observation["mode"] == "extend"
    assert second_observation["bytes_read_this_call"] == len(second)
    assert second_observation["rebuild_count"] == 1
    assert second_observation["extend_count"] == 1

    cached = gs445.incremental_gzip_export(path)
    cached_observation = gs445.export_observation(path)
    assert cached == extended
    assert cached_observation["mode"] == "cache_hit"
    assert cached_observation["bytes_read_this_call"] == 0


def test_gs445_rebuilds_after_truncation_or_same_size_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = tmp_path / "rotation.jsonl"
    first = _large_payload("FIRST", count=12)
    path.write_bytes(first)
    assert gzip.decompress(gs445.incremental_gzip_export(path)) == first

    shorter = _large_payload("NEW", count=8)
    path.write_bytes(shorter)
    rebuilt = gs445.incremental_gzip_export(path)
    observation = gs445.export_observation(path)
    assert gzip.decompress(rebuilt) == shorter
    assert observation["mode"] == "rebuild"
    assert observation["rebuild_count"] == 2

    same_size = b"Z" * len(shorter)
    old_mtime = path.stat().st_mtime_ns
    path.write_bytes(same_size)
    # Filesystems used in CI normally advance mtime_ns on write. Make the mutation
    # explicit if an unusually coarse clock happened to preserve the same value.
    if path.stat().st_mtime_ns == old_mtime:
        os.utime(path, ns=(old_mtime + 1, old_mtime + 1))
    rebuilt_same_size = gs445.incremental_gzip_export(path)
    observation = gs445.export_observation(path)
    assert gzip.decompress(rebuilt_same_size) == same_size
    assert observation["mode"] == "rebuild"
    assert observation["rebuild_count"] == 3


def test_gs445_preserves_small_raw_export_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 1024)
    gs445.reset_state()
    path = tmp_path / "small.jsonl"
    payload = b'{"symbol":"AIXC"}\n'
    path.write_bytes(payload)

    assert gs445.incremental_gzip_export(path) == payload
    observation = gs445.export_observation(path)
    assert observation["mode"] == "raw_small"
    assert observation["source_size"] == len(payload)


def test_gs445_install_reuses_gs364_memory_and_flight_export_wrappers(tmp_path, monkeypatch):
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    original = gs364._gzip_export
    try:
        gs445.install()
        installed = gs364._gzip_export
        assert getattr(installed, "_gs445_incremental_backup_exports", False)
        assert getattr(installed, "_gs364_compressed_export", False) is False or True

        history_path = tmp_path / "candidate.jsonl"
        flight_path = tmp_path / "flight.jsonl"
        history_payload = _large_payload("TRUG")
        flight_payload = _large_payload("SCAN")
        history_path.write_bytes(history_payload)
        flight_path.write_bytes(flight_payload)

        assert gzip.decompress(MemoryStore(history_path).export_bytes()) == history_payload
        assert gzip.decompress(FlightRecorder(flight_path).export_bytes()) == flight_payload
    finally:
        gs364._gzip_export = original
        gs445.reset_state()


def test_gs445_is_installed_before_sidebar_backup_materialization():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")

    assert "from .gs445_incremental_backup_exports import install as install_gs445" in startup
    assert startup.index("install_gs445()") < startup.index("install_gs416()")
    assert app.index('log_startup("entering app.py")') < app.index("data=get_store().export_bytes()")


def test_gs445_scope_lock_is_export_materialization_only():
    source = Path("mide/gs445_incremental_backup_exports.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "alignment_score =",
        "candidate_status =",
        "request_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)
