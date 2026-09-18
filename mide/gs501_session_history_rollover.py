"""GS501: rotate Candidate History at the next Eastern trading-session date.

Sept. 18 storage validation proved two distinct facts:
1. GS499/GS500 can keep new persisted rows bounded.
2. The already-written multi-gigabyte active Candidate History remains expensive to
   back up and scan until it is separated from the next session.

GS501 does not rewrite or truncate the live file. Before the first Candidate History
append on a new America/New_York calendar date, it atomically renames the prior active
file into data/session_archives/ and lets the normal append create a fresh active
candidate_history.jsonl. On the same date it does nothing.

Renaming on the same filesystem is metadata-only, so a multi-gigabyte prior session
does not need to be copied at the next open. The prior evidence remains on disk while
the active file and future session backups start small.

Persistence lifecycle only. No discovery, provider request, market data, indicator,
score, gate, ranking, qualification, readiness, alert, cadence, execution, or order
behavior changes.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading
from typing import Any

from .time_service import eastern_time


_MARKER = "_gs501_session_history_rollover"
_ROLLOVER_LOCK = threading.Lock()


def _archive_target(path: Path, session_date, *, archive_dir: Path | None = None) -> Path:
    directory = archive_dir or (path.parent / "session_archives")
    directory.mkdir(parents=True, exist_ok=True)
    base = directory / f"{path.stem}-{session_date.strftime('%Y%m%d')}{path.suffix}"
    if not base.exists():
        return base
    counter = 2
    while True:
        candidate = directory / (
            f"{path.stem}-{session_date.strftime('%Y%m%d')}-{counter}{path.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def roll_active_history_if_new_session(
    path: str | Path,
    *,
    now: datetime | None = None,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically archive a non-empty active file when its ET date is older."""
    active = Path(path)
    current_date = eastern_time(now).date()
    directory = Path(archive_dir) if archive_dir is not None else None

    with _ROLLOVER_LOCK:
        try:
            stat = active.stat()
        except FileNotFoundError:
            return {
                "rolled": False,
                "reason": "missing",
                "active_path": str(active),
                "current_date": current_date.isoformat(),
            }
        except OSError:
            return {
                "rolled": False,
                "reason": "stat_error",
                "active_path": str(active),
                "current_date": current_date.isoformat(),
            }

        if stat.st_size <= 0:
            return {
                "rolled": False,
                "reason": "empty",
                "active_path": str(active),
                "current_date": current_date.isoformat(),
            }

        prior_date = eastern_time(datetime.fromtimestamp(stat.st_mtime)).date()
        if prior_date >= current_date:
            return {
                "rolled": False,
                "reason": "same_session",
                "active_path": str(active),
                "prior_date": prior_date.isoformat(),
                "current_date": current_date.isoformat(),
            }

        target = _archive_target(active, prior_date, archive_dir=directory)
        active.replace(target)
        return {
            "rolled": True,
            "reason": "new_session",
            "active_path": str(active),
            "archive_path": str(target),
            "prior_date": prior_date.isoformat(),
            "current_date": current_date.isoformat(),
            "archived_bytes": int(stat.st_size),
        }


def install_for_store_class(store_class) -> None:
    current = store_class.append
    if getattr(current, _MARKER, False):
        return

    def append(self, records):
        if records:
            roll_active_history_if_new_session(self.path)
        return current(self, records)

    append.__name__ = getattr(current, "__name__", "append")
    append.__doc__ = getattr(current, "__doc__", None)
    append._gs501_session_history_rollover = True
    append._gs501_original = current
    store_class.append = append


def install() -> None:
    from . import memory

    install_for_store_class(memory.MemoryStore)
