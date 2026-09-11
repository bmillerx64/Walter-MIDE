import gzip
from pathlib import Path

from mide import gs364_live_operator_containment as gs364
from mide import gs445_incremental_backup_exports as gs445
from mide import gs448_deferred_flight_recorder_download as gs448
from mide.flight_recorder import FlightRecorder


def _large_payload() -> bytes:
    return (
        b'{"scan_id":"one","payload":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}\n'
        * 40
    )


def test_default_flight_recorder_is_deferred_without_eager_export(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = Path("data/flight_recorder.jsonl")
    path.parent.mkdir(parents=True)
    payload = _large_payload()
    path.write_bytes(payload)
    recorder = FlightRecorder()
    calls = []

    def exporter(active_recorder):
        calls.append(True)
        return gs445.incremental_gzip_export(Path(active_recorder.path))

    deferred = gs448.deferred_flight_recorder_export(exporter, recorder)

    assert callable(deferred)
    assert calls == []
    assert getattr(deferred, "_gs448_deferred_flight_recorder", False)
    assert getattr(deferred, "_gs448_gzip_payload", False)

    downloaded = deferred()
    assert calls == [True]
    assert downloaded[:2] == b"\x1f\x8b"
    assert gzip.decompress(downloaded) == payload


def test_custom_flight_recorder_keeps_historical_eager_bytes_contract(tmp_path):
    path = tmp_path / "explicit-flight-recorder.jsonl"
    payload = b'{"scan_id":"custom"}\n'
    path.write_bytes(payload)
    recorder = FlightRecorder(path)
    calls = []

    def exporter(active_recorder):
        calls.append(True)
        return Path(active_recorder.path).read_bytes()

    exported = gs448.deferred_flight_recorder_export(exporter, recorder)

    assert exported == payload
    assert calls == [True]
    assert not callable(exported)


def test_installed_export_wrapper_defers_only_default_recorder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = Path("data/flight_recorder.jsonl")
    path.parent.mkdir(parents=True)
    payload = _large_payload()
    path.write_bytes(payload)

    original = FlightRecorder.export_bytes
    try:
        gs448._install_flight_export()
        live = FlightRecorder()
        deferred = live.export_bytes()
        assert callable(deferred)
        assert gzip.decompress(deferred()) == payload

        custom_path = tmp_path / "custom.jsonl"
        custom_path.write_bytes(b'{"scan_id":"custom"}\n')
        custom = FlightRecorder(custom_path)
        assert custom.export_bytes() == custom_path.read_bytes()
    finally:
        FlightRecorder.export_bytes = original


def test_download_metadata_marks_large_deferred_recorder_as_gzip(monkeypatch):
    import streamlit as st

    captured = {}
    original = st.download_button

    def fake_download_button(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "ok"

    def deferred():
        return b"payload"

    deferred._gs448_deferred_flight_recorder = True
    deferred._gs448_gzip_payload = True

    try:
        monkeypatch.setattr(st, "download_button", fake_download_button)
        gs448._install_download_metadata()
        result = st.download_button(
            "Download Flight Recorder",
            data=deferred,
            file_name="flight_recorder.jsonl",
            mime="application/x-ndjson",
        )
        assert result == "ok"
        assert captured["kwargs"]["file_name"] == "flight_recorder.jsonl.gz"
        assert captured["kwargs"]["mime"] == "application/gzip"
        assert captured["kwargs"]["data"] is deferred
    finally:
        monkeypatch.setattr(st, "download_button", original)


def test_gs448_installs_after_gs446_and_before_sidebar_export():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")

    assert "from .gs448_deferred_flight_recorder_download import install as install_gs448" in startup
    assert startup.index("install_gs446()") < startup.index("install_gs448()")
    assert startup.index("install_gs448()") < startup.index("install_gs416()")
    assert app.index('log_startup("entering app.py")') < app.index(
        'data=flight_recorder_download_bytes(get_flight_recorder())'
    )


def test_gs448_scope_lock_is_export_memory_only():
    source = Path("mide/gs448_deferred_flight_recorder_download.py").read_text(
        encoding="utf-8"
    )
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
    assert 'AUTHORITY = "EXPORT_MEMORY_CONTAINMENT_ONLY"' in source
