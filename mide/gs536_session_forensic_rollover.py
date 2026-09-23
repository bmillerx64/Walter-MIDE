"""GS536: make forensic logs roll cleanly at each Eastern trading date.

Sept. 23 live backup exposed that the active Candidate History still began on Sept. 21
and Flight Recorder also remained cumulative. The resulting routine backup had grown
to about 2.23 GB of raw JSON / about 240 MB compressed and took several minutes to
prepare/upload.

GS501 relied on file mtime and converted a naive datetime.fromtimestamp value as
though it were already Eastern. On a UTC cloud host, a late-evening ET write can
therefore look like the next calendar date and suppress next-session rollover. Flight
Recorder had no session rollover at all.

GS536 uses the earliest embedded ISO timestamp near the beginning of each active JSONL
file as the primary session date, with a timezone-aware mtime fallback. It installs
the same metadata-only rollover before Candidate History append and Flight Recorder
record_scan. Prior files are atomically moved to data/session_archives; new active
files then start small.

Persistence/export lifecycle only. No market data, discovery, score, gate, ranking,
qualification, readiness, alert, cadence, execution, or order behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import re
import threading
from typing import Any

from .time_service import eastern_time

_MARKER_STORE = "_walter_gs536_candidate_rollover"
_MARKER_FLIGHT = "_walter_gs536_flight_rollover"
_LOCK = threading.Lock()
_ISO_RE = re.compile(
    rb"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)


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


def _embedded_session_date(path: Path):
    try:
        with path.open("rb") as handle:
            prefix = handle.read(256 * 1024)
    except OSError:
        return None
    match = _ISO_RE.search(prefix)
    if not match:
        return None
    text = match.group(0).decode("ascii").replace("Z", "+00:00")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return eastern_time(stamp).date()


def active_file_session_date(path: str | Path):
    active = Path(path)
    embedded = _embedded_session_date(active)
    if embedded is not None:
        return embedded
    try:
        stamp = datetime.fromtimestamp(active.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return eastern_time(stamp).date()


def roll_active_file_if_new_session(
    path: str | Path,
    *,
    now: datetime | None = None,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    active = Path(path)
    current_date = eastern_time(now).date()
    directory = Path(archive_dir) if archive_dir is not None else None

    with _LOCK:
        try:
            stat = active.stat()
        except FileNotFoundError:
            return {"rolled": False, "reason": "missing"}
        except OSError:
            return {"rolled": False, "reason": "stat_error"}
        if stat.st_size <= 0:
            return {"rolled": False, "reason": "empty"}

        prior_date = active_file_session_date(active)
        if prior_date is None:
            return {"rolled": False, "reason": "date_unknown"}
        if prior_date >= current_date:
            return {
                "rolled": False,
                "reason": "same_session",
                "prior_date": prior_date.isoformat(),
                "current_date": current_date.isoformat(),
            }

        target = _archive_target(active, prior_date, archive_dir=directory)
        active.replace(target)
        return {
            "rolled": True,
            "reason": "new_session",
            "archive_path": str(target),
            "prior_date": prior_date.isoformat(),
            "current_date": current_date.isoformat(),
            "archived_bytes": int(stat.st_size),
        }


def _install_store(store_class) -> None:
    current = store_class.append
    if getattr(current, _MARKER_STORE, False):
        return

    @wraps(current)
    def append(self, records):
        if records:
            roll_active_file_if_new_session(self.path)
        return current(self, records)

    setattr(append, _MARKER_STORE, True)
    append._gs536_original = current
    store_class.append = append


def _install_flight(recorder_class) -> None:
    current = recorder_class.record_scan
    if getattr(current, _MARKER_FLIGHT, False):
        return

    @wraps(current)
    def record_scan(self, *args, **kwargs):
        roll_active_file_if_new_session(self.path, now=kwargs.get("timestamp"))
        return current(self, *args, **kwargs)

    setattr(record_scan, _MARKER_FLIGHT, True)
    record_scan._gs536_original = current
    recorder_class.record_scan = record_scan


def install() -> None:
    from . import memory, flight_recorder

    _install_store(memory.MemoryStore)
    _install_flight(flight_recorder.FlightRecorder)
