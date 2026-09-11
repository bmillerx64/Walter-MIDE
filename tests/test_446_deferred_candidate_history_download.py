import gzip
from pathlib import Path

from mide import gs364_live_operator_containment as gs364
from mide import gs445_incremental_backup_exports as gs445
from mide import gs446_deferred_candidate_history_download as gs446
from mide.memory import MemoryStore


def _payload(symbol: str, count: int = 20) -> bytes:
    return (
        (f'{{"symbol":"{symbol}","evidence":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}}\n').encode()
        * count
    )


def test_live_default_history_is_deferred_without_eager_payload_work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = Path("data/candidate_history.jsonl")
    path.parent.mkdir(parents=True)
    payload = _payload("CHOW")
    path.write_bytes(payload)
    store = MemoryStore()
    calls = []

    def exporter(candidate_store):
        calls.append(Path(candidate_store.path).stat().st_size)
        return gs445.incremental_gzip_export(Path(candidate_store.path))

    deferred = gs446.deferred_candidate_history_export(exporter, store)

    assert callable(deferred)
    assert calls == []
    assert getattr(deferred, "_gs446_deferred_candidate_history", False)
    assert getattr(deferred, "_gs446_gzip_payload", False)
    file_name, mime = gs446.deferred_download_metadata(
        deferred,
        "candidate_history.jsonl",
        "application/x-ndjson",
    )
    assert file_name == "candidate_history.jsonl.gz"
    assert mime == "application/gzip"

    downloaded = deferred()
    assert len(calls) == 1
    assert downloaded[:2] == b"\x1f\x8b"
    assert gzip.decompress(downloaded) == payload


def test_custom_memory_store_keeps_historical_eager_bytes_contract(tmp_path):
    path = tmp_path / "explicit-history.jsonl"
    path.write_bytes(b'{"symbol":"AIXC"}\n')
    store = MemoryStore(path)
    calls = []

    def exporter(candidate_store):
        calls.append(True)
        return Path(candidate_store.path).read_bytes()

    exported = gs446.deferred_candidate_history_export(exporter, store)

    assert exported == path.read_bytes()
    assert calls == [True]
    assert not callable(exported)


def test_render_time_raw_mode_stays_raw_if_file_crosses_threshold_before_click(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 128)
    gs445.reset_state()
    path = Path("data/candidate_history.jsonl")
    path.parent.mkdir(parents=True)
    initial = b'{"symbol":"SMALL"}\n'
    path.write_bytes(initial)
    store = MemoryStore()

    deferred = gs446.deferred_candidate_history_export(
        lambda candidate_store: gs445.incremental_gzip_export(Path(candidate_store.path)),
        store,
    )
    assert callable(deferred)
    assert not getattr(deferred, "_gs446_gzip_payload", True)

    appended = _payload("LARGE", count=10)
    with path.open("ab") as handle:
        handle.write(appended)

    downloaded = deferred()
    assert downloaded == initial + appended
    file_name, mime = gs446.deferred_download_metadata(
        deferred,
        "candidate_history.jsonl",
        "application/x-ndjson",
    )
    assert file_name == "candidate_history.jsonl"
    assert mime == "application/x-ndjson"


def test_render_time_gzip_mode_stays_gzip_if_file_is_truncated_before_click(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gs364, "LARGE_EXPORT_BYTES", 64)
    gs445.reset_state()
    path = Path("data/candidate_history.jsonl")
    path.parent.mkdir(parents=True)
    path.write_bytes(_payload("LARGE"))
    store = MemoryStore()

    deferred = gs446.deferred_candidate_history_export(
        lambda candidate_store: gs445.incremental_gzip_export(Path(candidate_store.path)),
        store,
    )
    assert getattr(deferred, "_gs446_gzip_payload", False)

    replacement = b'{"symbol":"NEW"}\n'
    path.write_bytes(replacement)
    downloaded = deferred()

    assert downloaded[:2] == b"\x1f\x8b"
    assert gzip.decompress(downloaded) == replacement


def test_gs446_is_installed_after_gs445_before_app_sidebar_render():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    app = Path("app.py").read_text(encoding="utf-8")

    assert "from .gs446_deferred_candidate_history_download import install as install_gs446" in startup
    assert startup.index("install_gs445()") < startup.index("install_gs446()")
    assert startup.index("install_gs446()") < startup.index("install_gs416()")
    assert app.index('log_startup("entering app.py")') < app.index(
        '"Download Candidate History"'
    )


def test_gs446_preserves_sidebar_contract_and_existing_streamlit_pin():
    app = Path("app.py").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    start = app.index('"Download Candidate History"')
    block = app[start : start + 320]

    # app.py remains unchanged: its existing eager-looking call is intentionally
    # intercepted by the default MemoryStore wrapper and now returns a callable.
    assert "data=get_store().export_bytes()" in block
    assert 'file_name="candidate_history.jsonl"' in block
    assert 'mime="application/x-ndjson"' in block
    assert 'use_container_width=True' in block
    assert "streamlit==1.62.0" in requirements
    assert requirements.startswith("# GS445 deployment marker:")


def test_gs446_scope_lock_is_export_presentation_only():
    source = Path("mide/gs446_deferred_candidate_history_download.py").read_text(
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
    assert 'AUTHORITY = "EXPORT_PRESENTATION_LATENCY_ONLY"' in source
