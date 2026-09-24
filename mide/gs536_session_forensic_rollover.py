"""GS536: warm-deploy-safe Replay / Validation facade for forensic rollover.

GS536's Candidate History and Flight Recorder session rollover now lives in authoritative
Replay / Validation. This historical module retains the two validated wrapper markers,
the shared lock, and the embedded-ISO timestamp regex so existing runtime identity and
regression seams remain stable.

A stale warm Replay / Validation generation fails closed: active files are not moved,
wrapper installation no-ops, and no persistence content or trading behavior is changed.
No market data, discovery, score, gate, ranking, qualification, readiness, alert,
cadence, execution, or order behavior changes.
"""
from __future__ import annotations

from pathlib import Path
import re
import threading
from typing import Any


_MARKER_STORE = "_walter_gs536_candidate_rollover"
_MARKER_FLIGHT = "_walter_gs536_flight_rollover"
_LOCK = threading.Lock()
_ISO_RE = re.compile(
    rb"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
)


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _archive_target(
    path: Path,
    session_date,
    *,
    archive_dir: Path | None = None,
) -> Path:
    current = getattr(
        _replay(),
        "forensic_archive_target",
        None,
    )
    if not callable(current):
        return (
            (archive_dir or (path.parent / "session_archives"))
            / f"{path.stem}-{session_date.strftime('%Y%m%d')}{path.suffix}"
        )
    return current(
        path,
        session_date,
        archive_dir=archive_dir,
    )


def _embedded_session_date(path: Path):
    current = getattr(
        _replay(),
        "embedded_forensic_session_date",
        None,
    )
    if not callable(current):
        return None
    return current(path)


def active_file_session_date(path: str | Path):
    current = getattr(
        _replay(),
        "active_forensic_file_session_date",
        None,
    )
    if not callable(current):
        return None
    return current(path)


def roll_active_file_if_new_session(
    path: str | Path,
    *,
    now=None,
    archive_dir: str | Path | None = None,
) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "roll_active_forensic_file_if_new_session",
        None,
    )
    if not callable(current):
        return {
            "rolled": False,
            "reason": "Replay / Validation unavailable",
        }
    return current(
        path,
        now=now,
        archive_dir=archive_dir,
    )


def _install_store(store_class) -> None:
    current = getattr(
        _replay(),
        "install_forensic_store_rollover",
        None,
    )
    if callable(current):
        current(store_class)


def _install_flight(recorder_class) -> None:
    current = getattr(
        _replay(),
        "install_forensic_flight_rollover",
        None,
    )
    if callable(current):
        current(recorder_class)


def install() -> None:
    current = getattr(
        _replay(),
        "install_session_forensic_rollover",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "active_file_session_date",
    "roll_active_file_if_new_session",
    "install",
]
