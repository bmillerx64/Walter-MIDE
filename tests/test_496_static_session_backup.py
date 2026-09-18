from datetime import datetime, timezone
import json
from pathlib import Path
from zipfile import ZipFile

from mide import gs496_static_session_backup as gs496


def test_disk_backup_preserves_exact_captured_files_and_manifest(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    candidate_bytes = b'{"symbol":"MRNO"}\n' * 1000
    flight_bytes = b'{"scan_id":"one"}\n' * 2000
    candidate.write_bytes(candidate_bytes)
    flight.write_bytes(flight_bytes)

    info = gs496.build_session_backup_archive(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        now=datetime(2026, 9, 18, 17, 0, tzinfo=timezone.utc),
        token="fixed",
    )

    archive_path = tmp_path / "static" / info["filename"]
    assert archive_path.exists()
    assert info["source_bytes_total"] == len(candidate_bytes) + len(flight_bytes)
    assert info["archive_bytes"] == archive_path.stat().st_size
    assert info["href"].endswith(info["filename"])

    with ZipFile(archive_path) as archive:
        assert archive.read("candidate_history.jsonl") == candidate_bytes
        assert archive.read("flight_recorder.jsonl") == flight_bytes
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["authority"] == gs496.AUTHORITY
    assert manifest["candidate_history_bytes"] == len(candidate_bytes)
    assert manifest["flight_recorder_bytes"] == len(flight_bytes)
    assert manifest["trading_logic_changed"] is False


def test_snapshot_member_reads_only_requested_prefix(tmp_path):
    source = tmp_path / "growing.jsonl"
    source.write_bytes(b"first\nsecond\nthird\n")
    target = tmp_path / "snapshot.zip"

    with ZipFile(target, "w") as archive:
        copied = gs496._write_snapshot_member(
            archive,
            source,
            "growing.jsonl",
            captured_size=len(b"first\nsecond\n"),
            chunk_bytes=5,
        )

    assert copied == len(b"first\nsecond\n")
    with ZipFile(target) as archive:
        assert archive.read("growing.jsonl") == b"first\nsecond\n"


def test_new_backup_replaces_prior_generated_archive(tmp_path):
    candidate = tmp_path / "candidate.jsonl"
    flight = tmp_path / "flight.jsonl"
    candidate.write_bytes(b"one\n")
    flight.write_bytes(b"two\n")
    output = tmp_path / "static"

    first = gs496.build_session_backup_archive(
        candidate, flight, output_dir=output, token="one"
    )
    second = gs496.build_session_backup_archive(
        candidate, flight, output_dir=output, token="two"
    )

    assert not (output / first["filename"]).exists()
    assert (output / second["filename"]).exists()


def test_link_is_static_download_not_streamlit_download_widget():
    info = {
        "filename": "walter-session-backup-test.zip",
        "href": "app/static/walter-session-backup-test.zip",
        "archive_bytes": 2 * 1024 * 1024,
        "source_bytes_total": 20 * 1024 * 1024,
    }
    markup = gs496.backup_link_markup(info)
    assert 'href="app/static/walter-session-backup-test.zip"' in markup
    assert 'download="walter-session-backup-test.zip"' in markup
    assert "st.download_button(" not in Path(
        "mide/gs496_static_session_backup.py"
    ).read_text(encoding="utf-8")


def test_live_app_uses_gs496_and_static_serving():
    app = Path("app.py").read_text(encoding="utf-8")
    config = Path(".streamlit/config.toml").read_text(encoding="utf-8")

    assert "render_session_backup_controls" in app
    assert 'st.download_button(\n        "Download Candidate History"' not in app
    assert 'st.download_button(\n        "Download Flight Recorder"' not in app
    assert "enableStaticServing = true" in config


def test_scope_lock_is_export_only():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
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
        "submit_order(",
    )
    assert not any(token in source for token in forbidden)
    assert 'AUTHORITY = "STATIC_DISK_SESSION_BACKUP_ONLY"' in source
