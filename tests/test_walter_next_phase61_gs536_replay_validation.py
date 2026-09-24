"""Phase 61: GS536 forensic rollover belongs to Replay / Validation."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from mide import gs536_session_forensic_rollover as gs536
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_phase61_historical_marker_and_parser_seams_are_preserved():
    assert gs536._MARKER_STORE == "_walter_gs536_candidate_rollover"
    assert gs536._MARKER_FLIGHT == "_walter_gs536_flight_rollover"
    assert gs536._ISO_RE.search(b"2026-09-23T18:00:00+00:00")
    assert gs536._LOCK is not None


def test_phase61_replay_authority_preserves_embedded_timestamp_truth(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    path.write_text(
        '{"timestamp":"2026-09-22T18:00:00+00:00","symbol":"ABC"}\n',
        encoding="utf-8",
    )

    assert gs536.active_file_session_date(path).isoformat() == "2026-09-22"
    result = gs536.roll_active_file_if_new_session(
        path,
        now=datetime(
            2026,
            9,
            23,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )
    assert result["rolled"] is True
    assert Path(result["archive_path"]).exists()


def test_phase61_stale_replay_generation_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(gs536, "_replay", lambda: SimpleNamespace())

    path = tmp_path / "flight_recorder.jsonl"
    path.write_text(
        '{"timestamp":"2026-09-22T18:00:00+00:00"}\n',
        encoding="utf-8",
    )

    assert gs536.active_file_session_date(path) is None
    result = gs536.roll_active_file_if_new_session(
        path,
        now=datetime(
            2026,
            9,
            23,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )
    assert result["rolled"] is False
    assert path.exists()
    assert gs536.install() is None


def test_phase61_facade_is_lazy_and_replay_owns_implementation():
    facade = (
        ROOT / "mide/gs536_session_forensic_rollover.py"
    ).read_text(encoding="utf-8")
    replay = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def _replay(" in facade
    assert "from mide.authorities import replay_validation as" not in facade

    for name in (
        "forensic_archive_target",
        "embedded_forensic_session_date",
        "active_forensic_file_session_date",
        "roll_active_forensic_file_if_new_session",
        "install_forensic_store_rollover",
        "install_forensic_flight_rollover",
        "install_session_forensic_rollover",
    ):
        assert f"def {name}(" in replay

    assert "active.replace(target)" not in facade
    assert "@wraps(current)" not in facade


def test_phase61_scope_is_persistence_lifecycle_only():
    replay = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    start = replay.index("# GS536 session-forensic persistence rollover")
    end = replay.index("# GS425 live-scan latency truth recorder", start)
    block = replay[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
    assert 'FORENSIC_ROLLOVER_AUTHORITY = "REPLAY_PERSISTENCE_LIFECYCLE_ONLY"' in block


def test_phase61_wrapper_markers_are_preserved_after_install():
    from mide.flight_recorder import FlightRecorder
    from mide.memory import MemoryStore

    gs536.install()

    assert getattr(
        MemoryStore.append,
        gs536._MARKER_STORE,
        False,
    )
    assert getattr(
        FlightRecorder.record_scan,
        gs536._MARKER_FLIGHT,
        False,
    )
