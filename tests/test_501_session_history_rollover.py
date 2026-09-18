from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from mide.gs501_session_history_rollover import (
    install_for_store_class,
    roll_active_history_if_new_session,
)


ET = ZoneInfo("America/New_York")


def _set_mtime(path: Path, when: datetime) -> None:
    stamp = when.timestamp()
    os.utime(path, (stamp, stamp))


def test_same_eastern_date_does_not_rotate(tmp_path):
    active = tmp_path / "candidate_history.jsonl"
    active.write_text('{"symbol":"A"}\n', encoding="utf-8")
    _set_mtime(active, datetime(2026, 9, 18, 15, 30, tzinfo=ET))

    result = roll_active_history_if_new_session(
        active,
        now=datetime(2026, 9, 18, 19, 0, tzinfo=ET),
    )

    assert result["rolled"] is False
    assert result["reason"] == "same_session"
    assert active.exists()


def test_new_eastern_date_atomically_archives_prior_active_file(tmp_path):
    active = tmp_path / "candidate_history.jsonl"
    payload = '{"symbol":"A"}\n{"symbol":"B"}\n'
    active.write_text(payload, encoding="utf-8")
    _set_mtime(active, datetime(2026, 9, 18, 19, 59, tzinfo=ET))

    result = roll_active_history_if_new_session(
        active,
        now=datetime(2026, 9, 21, 4, 1, tzinfo=ET),
    )

    archive = tmp_path / "session_archives" / "candidate_history-20260918.jsonl"
    assert result["rolled"] is True
    assert result["archive_path"] == str(archive)
    assert archive.read_text(encoding="utf-8") == payload
    assert not active.exists()


def test_existing_archive_name_gets_collision_safe_suffix(tmp_path):
    active = tmp_path / "candidate_history.jsonl"
    active.write_text("new\n", encoding="utf-8")
    _set_mtime(active, datetime(2026, 9, 18, 18, 0, tzinfo=ET))
    archive_dir = tmp_path / "session_archives"
    archive_dir.mkdir()
    (archive_dir / "candidate_history-20260918.jsonl").write_text(
        "older\n", encoding="utf-8"
    )

    result = roll_active_history_if_new_session(
        active,
        now=datetime(2026, 9, 21, 4, 0, tzinfo=ET),
    )

    assert result["archive_path"].endswith("candidate_history-20260918-2.jsonl")
    assert Path(result["archive_path"]).read_text(encoding="utf-8") == "new\n"


def test_store_wrapper_rotates_then_normal_append_creates_fresh_active_file(tmp_path, monkeypatch):
    active = tmp_path / "candidate_history.jsonl"
    active.write_text('{"symbol":"OLD"}\n', encoding="utf-8")
    _set_mtime(active, datetime(2026, 9, 18, 15, 0, tzinfo=ET))

    from mide import gs501_session_history_rollover as gs501
    monkeypatch.setattr(
        gs501,
        "eastern_time",
        lambda value=None: datetime(2026, 9, 21, 4, 5, tzinfo=ET),
    )

    class Store:
        def __init__(self, path):
            self.path = Path(path)

        def append(self, records):
            with self.path.open("a", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")

    install_for_store_class(Store)
    Store(active).append([{"symbol": "NEW"}])

    archive = tmp_path / "session_archives" / "candidate_history-20260918.jsonl"
    assert archive.read_text(encoding="utf-8") == '{"symbol":"OLD"}\n'
    assert active.read_text(encoding="utf-8") == '{"symbol": "NEW"}\n'


def test_store_wrapper_is_idempotent():
    class Store:
        calls = 0

        def __init__(self):
            self.path = Path("missing.jsonl")

        def append(self, records):
            type(self).calls += 1

    install_for_store_class(Store)
    first = Store.append
    install_for_store_class(Store)
    assert Store.append is first

    Store().append([])
    assert Store.calls == 1


def test_app_hard_binds_rollover_after_gs500_before_memory_store_import():
    app = Path("app.py").read_text(encoding="utf-8")
    bind = "from mide.gs501_session_history_rollover import install as _install_gs501_history_rollover"
    call = "_install_gs501_history_rollover()"
    gs500_call = "_install_gs500_candidate_history()"
    memory_import = "from mide.memory import MemoryStore"

    assert bind in app
    assert call in app
    assert app.index(gs500_call) < app.index(call) < app.index(memory_import)


def test_scope_lock_is_persistence_lifecycle_only():
    source = Path("mide/gs501_session_history_rollover.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
