"""GS496: move live session backups out of Streamlit's in-memory download path.

Sept. 18 live validation isolated an operational failure: while AutoScan remained
active, clicking Candidate History / Flight Recorder caused process RSS to climb from
roughly 1.9 GiB to more than 2.5 GiB across reruns before Community Cloud terminated
the process. The trading pipeline itself continued through Mission Ranking until the
container died.

GS496 removes only the live sidebar backup transport from st.download_button.
When the operator asks for a backup, Walter snapshots the current Candidate History
and Flight Recorder file sizes, streams exactly those bytes into one ZIP on disk in
bounded chunks, and exposes the completed archive through Streamlit static-file
serving. The browser therefore downloads the archive from disk instead of requiring
Streamlit to retain a growing Python bytes payload/widget version in process memory.

The historical GS364/GS445/GS446/GS448/GS454/GS458 export helpers remain installed
for compatibility/tests, but the production sidebar no longer routes the two growing
session files through them.

Operational/export containment only. No provider request, market-data value,
discovery, VWAP, SuperTrend, participation, expansion, scoring, ranking,
qualification, alert/audio, execution, cadence predicate, or order behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import secrets
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


AUTHORITY = "STATIC_DISK_SESSION_BACKUP_ONLY"
STATIC_DIR = Path("static")
BACKUP_PREFIX = "walter-session-backup-"
CHUNK_BYTES = 1024 * 1024
SESSION_KEY = "_walter_gs496_session_backup"


def _captured_size(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.exists() else 0
    except OSError:
        return 0


def _write_snapshot_member(
    archive: ZipFile,
    source: Path,
    arcname: str,
    *,
    captured_size: int,
    chunk_bytes: int = CHUNK_BYTES,
) -> int:
    """Copy exactly the captured prefix of one append-only file into the ZIP."""
    remaining = max(0, int(captured_size))
    copied = 0
    with archive.open(arcname, "w") as target:
        if remaining <= 0 or not source.exists():
            return 0
        with source.open("rb") as handle:
            while remaining > 0:
                chunk = handle.read(min(max(1, int(chunk_bytes)), remaining))
                if not chunk:
                    break
                target.write(chunk)
                copied += len(chunk)
                remaining -= len(chunk)
    if copied != captured_size:
        raise RuntimeError(
            f"backup source changed unexpectedly while reading {arcname}: "
            f"captured={captured_size} copied={copied}"
        )
    return copied


def _remove_prior_archives(directory: Path, *, keep: Path) -> None:
    for candidate in directory.glob(f"{BACKUP_PREFIX}*.zip"):
        if candidate == keep:
            continue
        try:
            candidate.unlink()
        except OSError:
            pass


def build_session_backup_archive(
    candidate_history_path: str | Path,
    flight_recorder_path: str | Path,
    *,
    output_dir: str | Path = STATIC_DIR,
    now: datetime | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Create one bounded-memory, point-in-time ZIP snapshot on disk."""
    candidate_path = Path(candidate_history_path)
    flight_path = Path(flight_recorder_path)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    captured = {
        "candidate_history.jsonl": _captured_size(candidate_path),
        "flight_recorder.jsonl": _captured_size(flight_path),
    }
    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    suffix = str(token or secrets.token_hex(4)).replace("/", "")[:24] or "backup"
    filename = (
        f"{BACKUP_PREFIX}{instant.strftime('%Y%m%dT%H%M%SZ')}-{suffix}.zip"
    )
    target = directory / filename
    temporary = directory / (filename + ".tmp")

    try:
        with ZipFile(
            temporary,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=5,
            allowZip64=True,
        ) as archive:
            copied_candidate = _write_snapshot_member(
                archive,
                candidate_path,
                "candidate_history.jsonl",
                captured_size=captured["candidate_history.jsonl"],
            )
            copied_flight = _write_snapshot_member(
                archive,
                flight_path,
                "flight_recorder.jsonl",
                captured_size=captured["flight_recorder.jsonl"],
            )
            manifest = {
                "authority": AUTHORITY,
                "generated_at_utc": instant.isoformat(),
                "candidate_history_bytes": copied_candidate,
                "flight_recorder_bytes": copied_flight,
                "source_bytes_total": copied_candidate + copied_flight,
                "trading_logic_changed": False,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
            )
        temporary.replace(target)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass

    _remove_prior_archives(directory, keep=target)
    archive_bytes = _captured_size(target)
    return {
        "authority": AUTHORITY,
        "filename": filename,
        "href": f"app/static/{filename}",
        "generated_at_utc": instant.isoformat(),
        "candidate_history_bytes": captured["candidate_history.jsonl"],
        "flight_recorder_bytes": captured["flight_recorder.jsonl"],
        "source_bytes_total": sum(captured.values()),
        "archive_bytes": archive_bytes,
        "trading_logic_changed": False,
    }


def backup_link_markup(info: dict[str, Any]) -> str:
    filename = html.escape(str(info.get("filename") or ""), quote=True)
    href = html.escape(str(info.get("href") or ""), quote=True)
    archive_mb = float(info.get("archive_bytes") or 0) / (1024 * 1024)
    source_mb = float(info.get("source_bytes_total") or 0) / (1024 * 1024)
    return (
        '<a href="' + href + '" download="' + filename + '" '
        'style="display:block;text-align:center;padding:0.55rem 0.75rem;'
        'border:1px solid rgba(250,250,250,.25);border-radius:0.5rem;'
        'text-decoration:none;font-weight:600;">'
        f'⬇ Download prepared backup ({archive_mb:.1f} MB ZIP / {source_mb:.1f} MB source)'
        "</a>"
    )


def _render_backup_controls(candidate_history_path: Path, flight_recorder_path: Path) -> None:
    import streamlit as st

    st.caption(
        "Safe backup uses a disk-backed ZIP so large recorder/history bytes are not "
        "registered in Streamlit widget memory."
    )
    if st.button(
        "Prepare Session Backup",
        key="walter-gs496-prepare-session-backup",
        width="stretch",
    ):
        with st.spinner("Preparing point-in-time backup…"):
            st.session_state[SESSION_KEY] = build_session_backup_archive(
                candidate_history_path,
                flight_recorder_path,
            )

    info = st.session_state.get(SESSION_KEY)
    if not isinstance(info, dict):
        return
    filename = str(info.get("filename") or "")
    if not filename or not (STATIC_DIR / filename).exists():
        st.session_state.pop(SESSION_KEY, None)
        return
    st.markdown(backup_link_markup(info), unsafe_allow_html=True)
    st.caption(
        "Prepared at "
        + str(info.get("generated_at_utc") or "")
        + ". Prepare again whenever you need a newer snapshot."
    )


def render_session_backup_controls(
    candidate_history_path: str | Path,
    flight_recorder_path: str | Path,
) -> None:
    """Render backup controls in a fragment so backup clicks do not rerun Walter."""
    import streamlit as st

    candidate_path = Path(candidate_history_path)
    flight_path = Path(flight_recorder_path)

    fragment = getattr(st, "fragment", None)
    if not callable(fragment):
        _render_backup_controls(candidate_path, flight_path)
        return

    @fragment
    def backup_fragment() -> None:
        _render_backup_controls(candidate_path, flight_path)

    backup_fragment()
