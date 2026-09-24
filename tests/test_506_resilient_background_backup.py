from datetime import datetime, timezone
from pathlib import Path
from time import sleep, monotonic
from zipfile import ZipFile

from mide import gs496_static_session_backup as gs496


UTC = timezone.utc


def test_background_backup_completes_without_blocking_caller(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    candidate.write_bytes(b'{"symbol":"A"}\n' * 5000)
    flight.write_bytes(b'{"scan_id":"one"}\n' * 2000)

    started = monotonic()
    job = gs496.start_session_backup_job(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        now=datetime(2026, 9, 18, 21, 0, tzinfo=UTC),
    )
    returned_in = monotonic() - started

    assert returned_in < 0.5
    assert job["status"] == "running"
    assert job["source_bytes_total"] == candidate.stat().st_size + flight.stat().st_size

    deadline = monotonic() + 5
    status = None
    while monotonic() < deadline:
        status = gs496.session_backup_job_status(job["job_id"])
        if status and status.get("status") != "running":
            break
        sleep(0.02)

    assert status is not None
    assert status["status"] == "completed"
    info = status["result"]
    archive = tmp_path / "static" / info["filename"]
    assert archive.exists()
    with ZipFile(archive) as zipped:
        assert zipped.read("candidate_history.jsonl") == candidate.read_bytes()
        assert zipped.read("flight_recorder.jsonl") == flight.read_bytes()


def test_captured_sizes_keep_point_in_time_prefix_when_source_grows(tmp_path):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    initial_candidate = b'{"symbol":"OLD"}\n' * 100
    initial_flight = b'{"scan":"OLD"}\n' * 100
    candidate.write_bytes(initial_candidate)
    flight.write_bytes(initial_flight)

    captured = {
        "candidate_history.jsonl": len(initial_candidate),
        "flight_recorder.jsonl": len(initial_flight),
    }
    with candidate.open("ab") as handle:
        handle.write(b'{"symbol":"NEW"}\n' * 100)
    with flight.open("ab") as handle:
        handle.write(b'{"scan":"NEW"}\n' * 100)

    info = gs496.build_session_backup_archive(
        candidate,
        flight,
        output_dir=tmp_path / "static",
        now=datetime(2026, 9, 18, 21, 1, tzinfo=UTC),
        token="captured",
        captured_sizes=captured,
    )

    archive = tmp_path / "static" / info["filename"]
    with ZipFile(archive) as zipped:
        assert zipped.read("candidate_history.jsonl") == initial_candidate
        assert zipped.read("flight_recorder.jsonl") == initial_flight


def test_failed_background_job_surfaces_safe_status(tmp_path, monkeypatch):
    candidate = tmp_path / "candidate_history.jsonl"
    flight = tmp_path / "flight_recorder.jsonl"
    candidate.write_text("one\n", encoding="utf-8")
    flight.write_text("two\n", encoding="utf-8")

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic backup failure")

    monkeypatch.setattr(gs496, "build_session_backup_archive", fail)
    job = gs496.start_session_backup_job(
        candidate,
        flight,
        output_dir=tmp_path / "static",
    )

    deadline = monotonic() + 3
    status = None
    while monotonic() < deadline:
        status = gs496.session_backup_job_status(job["job_id"])
        if status and status.get("status") == "failed":
            break
        sleep(0.01)

    assert status is not None
    assert status["status"] == "failed"
    assert status["error_type"] == "RuntimeError"
    assert "synthetic backup failure" in status["error_message"]


def test_backup_fragment_polls_only_while_background_job_runs():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")

    assert "fragment(run_every=JOB_POLL_SECONDS)(backup_fragment)()" in source
    assert "fragment(backup_fragment)()" in source
    assert "if polling:" in source
    assert 'st.rerun(scope="app")' in source
    assert "@fragment(run_every=JOB_POLL_SECONDS)" not in source
    assert "start_session_backup_job(" in source
    assert "AutoScan can keep running." in source
    assert "with st.spinner(" not in source


def test_gs506_forces_clean_runtime_without_breaking_gs445_marker_contract():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert requirements.startswith("# GS445 deployment marker:")
    assert "# GS506 deployment marker:" in requirements


def test_scope_lock_remains_backup_transport_only():
    source = Path("mide/gs496_static_session_backup.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
