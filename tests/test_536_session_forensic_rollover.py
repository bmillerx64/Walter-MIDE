from datetime import datetime, timezone
from pathlib import Path

from mide.gs536_session_forensic_rollover import (
    active_file_session_date,
    roll_active_file_if_new_session,
)


def test_embedded_timestamp_beats_cloud_host_mtime(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    path.write_text(
        '{"symbol":"ABC","architecture_audit":[{"timestamp":"2026-09-21T17:05:21.531828Z"}]}\n',
        encoding="utf-8",
    )
    assert active_file_session_date(path).isoformat() == "2026-09-21"


def test_old_active_file_rolls_atomically_for_new_et_session(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    path.write_text(
        '{"timestamp":"2026-09-22T18:00:00+00:00","symbol":"ABC"}\n',
        encoding="utf-8",
    )
    result = roll_active_file_if_new_session(
        path,
        now=datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc),
    )
    assert result["rolled"] is True
    assert not path.exists()
    archived = Path(result["archive_path"])
    assert archived.exists()
    assert archived.parent.name == "session_archives"


def test_same_session_file_is_not_rolled(tmp_path):
    path = tmp_path / "flight_recorder.jsonl"
    path.write_text(
        '{"timestamp":"2026-09-23T12:55:00+00:00","scan_id":"x"}\n',
        encoding="utf-8",
    )
    result = roll_active_file_if_new_session(
        path,
        now=datetime(2026, 9, 23, 13, 0, tzinfo=timezone.utc),
    )
    assert result["rolled"] is False
    assert result["reason"] == "same_session"
    assert path.exists()


def test_timezone_aware_mtime_fallback_does_not_promote_utc_date(tmp_path):
    path = tmp_path / "emptyish.jsonl"
    path.write_text("no timestamp here\n", encoding="utf-8")
    epoch = datetime(2026, 9, 23, 0, 30, tzinfo=timezone.utc).timestamp()
    import os
    os.utime(path, (epoch, epoch))
    assert active_file_session_date(path).isoformat() == "2026-09-22"


def test_install_wraps_candidate_and_flight_without_trading_logic():
    from mide import gs536_session_forensic_rollover as gs536
    from mide.memory import MemoryStore
    from mide.flight_recorder import FlightRecorder

    gs536.install()
    assert getattr(MemoryStore.append, "_walter_gs536_candidate_rollover", False)
    assert getattr(FlightRecorder.record_scan, "_walter_gs536_flight_rollover", False)
