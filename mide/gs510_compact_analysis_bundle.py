"""GS510: produce a compact end-of-session forensic bundle for ChatGPT analysis.

The full Sept. 18 backup proved Walter can now build a multi-gigabyte point-in-time
archive, but the resulting ~288 MB browser/upload payload is unnecessarily large for
routine review. Candidate History's growth is dominated by cumulative history arrays
that are repeated inside later point-in-time rows.

GS510 adds a separate *analysis* bundle. It never replaces the full archival backup.

The compact candidate stream preserves every row and every current point-in-time field
except four cumulative arrays whose evidence is already represented by the sequence of
rows themselves:
- architecture_audit
- ranking_history
- discovery_history
- reevaluation_history

The exact point-in-time Flight Recorder is retained in full. A manifest records the
source byte sizes, row count, stripped fields and compact archive size.

This is export/forensics only. No scanner, provider, score, rank, qualification, alert,
cadence, execution or order behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import threading
from time import monotonic
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .gs496_static_session_backup import _write_snapshot_member


AUTHORITY = "COMPACT_ANALYSIS_BUNDLE_ONLY"
STATIC_DIR = Path("app/static")
SESSION_KEY = "_walter_gs510_analysis_bundle"
JOB_SESSION_KEY = "_walter_gs510_analysis_job_id"
JOB_POLL_SECONDS = 2.0
STRIPPED_CUMULATIVE_FIELDS = (
    "architecture_audit",
    "ranking_history",
    "discovery_history",
    "reevaluation_history",
)
_JOB_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _captured_size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _cleanup(directory: Path, keep: str) -> None:
    for prior in directory.glob("walter-analysis-bundle-*.zip"):
        if prior.name == keep:
            continue
        try:
            prior.unlink()
        except OSError:
            pass


def _compact_candidate_rows(
    archive: ZipFile,
    source: Path,
    *,
    captured_size: int,
) -> dict[str, int]:
    rows = 0
    malformed_rows = 0
    source_bytes_read = 0
    compact_bytes_written = 0

    with archive.open(
        "candidate_history_compact.jsonl",
        "w",
        force_zip64=True,
    ) as target:
        if captured_size <= 0 or not source.exists():
            return {
                "candidate_rows": 0,
                "candidate_malformed_rows": 0,
                "candidate_source_bytes_read": 0,
                "candidate_compact_bytes_written": 0,
            }

        remaining = int(captured_size)
        with source.open("rb") as handle:
            while remaining > 0:
                line = handle.readline(remaining)
                if not line:
                    break
                source_bytes_read += len(line)
                remaining -= len(line)

                # A stat can theoretically land mid-append. Do not manufacture a
                # partial JSON row in the forensic bundle.
                if not line.endswith(b"\n") and remaining == 0:
                    break
                try:
                    record = json.loads(line)
                except Exception:
                    malformed_rows += 1
                    continue
                for field in STRIPPED_CUMULATIVE_FIELDS:
                    record.pop(field, None)
                payload = (
                    json.dumps(record, separators=(",", ":"), ensure_ascii=False)
                    + "\n"
                ).encode("utf-8")
                target.write(payload)
                compact_bytes_written += len(payload)
                rows += 1

    return {
        "candidate_rows": rows,
        "candidate_malformed_rows": malformed_rows,
        "candidate_source_bytes_read": source_bytes_read,
        "candidate_compact_bytes_written": compact_bytes_written,
    }


def build_analysis_bundle(
    candidate_history_path: str | Path,
    flight_recorder_path: str | Path,
    *,
    output_dir: str | Path = STATIC_DIR,
    now: datetime | None = None,
    token: str | None = None,
    captured_sizes: dict[str, int] | None = None,
) -> dict[str, Any]:
    candidate_path = Path(candidate_history_path)
    flight_path = Path(flight_recorder_path)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    captured = dict(captured_sizes or {})
    if not captured:
        captured = {
            "candidate_history.jsonl": _captured_size(candidate_path),
            "flight_recorder.jsonl": _captured_size(flight_path),
        }

    instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    safe_token = token or secrets.token_hex(10)
    filename = (
        "walter-analysis-bundle-"
        + instant.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + safe_token
        + ".zip"
    )
    final_path = directory / filename
    temporary_path = directory / (filename + ".part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with ZipFile(
            temporary_path,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            candidate_stats = _compact_candidate_rows(
                archive,
                candidate_path,
                captured_size=int(captured.get("candidate_history.jsonl") or 0),
            )
            flight_bytes = _write_snapshot_member(
                archive,
                flight_path,
                "flight_recorder.jsonl",
                captured_size=int(captured.get("flight_recorder.jsonl") or 0),
            )
            manifest = {
                "authority": AUTHORITY,
                "generated_at_utc": instant.isoformat(),
                "candidate_history_source_bytes": int(
                    captured.get("candidate_history.jsonl") or 0
                ),
                "flight_recorder_source_bytes": int(
                    captured.get("flight_recorder.jsonl") or 0
                ),
                "source_bytes_total": sum(int(v or 0) for v in captured.values()),
                "flight_recorder_bytes_copied": int(flight_bytes),
                "stripped_cumulative_fields": list(STRIPPED_CUMULATIVE_FIELDS),
                "candidate_history_semantics": (
                    "every complete point-in-time row retained; only repeated "
                    "cumulative history arrays removed"
                ),
                "flight_recorder_semantics": "exact captured point-in-time prefix",
                "trading_logic_changed": False,
                **candidate_stats,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2, sort_keys=True),
            )
        temporary_path.replace(final_path)
    except Exception:
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise

    _cleanup(directory, filename)
    archive_bytes = int(final_path.stat().st_size)
    return {
        "authority": AUTHORITY,
        "filename": filename,
        "path": str(final_path),
        "archive_bytes": archive_bytes,
        "source_bytes_total": int(sum(int(v or 0) for v in captured.values())),
        "generated_at_utc": instant.isoformat(),
        "candidate_rows": int(candidate_stats["candidate_rows"]),
        "candidate_compact_bytes": int(
            candidate_stats["candidate_compact_bytes_written"]
        ),
        "stripped_fields": list(STRIPPED_CUMULATIVE_FIELDS),
        "trading_logic_changed": False,
    }


def _job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _JOB_LOCK:
        job = _JOBS.get(str(job_id))
        return dict(job) if isinstance(job, dict) else None


def _set_job(job_id: str, **updates: Any) -> None:
    with _JOB_LOCK:
        _JOBS.setdefault(str(job_id), {}).update(updates)


def start_analysis_bundle_job(
    candidate_history_path: str | Path,
    flight_recorder_path: str | Path,
    *,
    output_dir: str | Path = STATIC_DIR,
) -> dict[str, Any]:
    candidate_path = Path(candidate_history_path)
    flight_path = Path(flight_recorder_path)
    captured = {
        "candidate_history.jsonl": _captured_size(candidate_path),
        "flight_recorder.jsonl": _captured_size(flight_path),
    }
    instant = datetime.now(timezone.utc)
    job_id = secrets.token_hex(12)
    started = monotonic()
    initial = {
        "job_id": job_id,
        "status": "running",
        "started_at_utc": instant.isoformat(),
        "source_bytes_total": sum(captured.values()),
        "elapsed_seconds": 0.0,
        "trading_logic_changed": False,
    }
    with _JOB_LOCK:
        _JOBS[job_id] = dict(initial)

    def worker() -> None:
        try:
            info = build_analysis_bundle(
                candidate_path,
                flight_path,
                output_dir=output_dir,
                now=instant,
                token=job_id,
                captured_sizes=captured,
            )
        except Exception as exc:
            _set_job(
                job_id,
                status="failed",
                finished_at_utc=datetime.now(timezone.utc).isoformat(),
                elapsed_seconds=round(monotonic() - started, 2),
                error_type=type(exc).__name__,
                error_message=str(exc)[:500],
            )
            return
        _set_job(
            job_id,
            status="completed",
            finished_at_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=round(monotonic() - started, 2),
            result=info,
        )

    threading.Thread(
        target=worker,
        name=f"walter-analysis-bundle-{job_id[:8]}",
        daemon=True,
    ).start()
    return initial


def analysis_bundle_job_status(job_id: str) -> dict[str, Any] | None:
    job = _job_snapshot(job_id)
    if not isinstance(job, dict):
        return None
    if job.get("status") == "running":
        started_at = str(job.get("started_at_utc") or "")
        try:
            started_dt = datetime.fromisoformat(started_at)
            elapsed = datetime.now(timezone.utc) - started_dt.astimezone(timezone.utc)
            job["elapsed_seconds"] = max(0.0, round(elapsed.total_seconds(), 1))
        except Exception:
            pass
    return job


def _render(candidate_path: Path, flight_path: Path) -> None:
    import streamlit as st

    st.caption(
        "Compact analysis bundle: full Flight Recorder + every Candidate History row, "
        "with only four repeated cumulative history arrays removed."
    )

    job_id = str(st.session_state.get(JOB_SESSION_KEY) or "")
    job = analysis_bundle_job_status(job_id) if job_id else None
    running = bool(job and job.get("status") == "running")

    if st.button(
        "Prepare Compact Analysis Bundle",
        key="walter-gs510-prepare-analysis-bundle",
        width="stretch",
        disabled=running,
    ):
        job = start_analysis_bundle_job(candidate_path, flight_path)
        st.session_state[JOB_SESSION_KEY] = str(job["job_id"])
        st.session_state.pop(SESSION_KEY, None)
        running = True

    if running and isinstance(job, dict):
        source_mb = float(job.get("source_bytes_total") or 0) / (1024 * 1024)
        elapsed = float(job.get("elapsed_seconds") or 0)
        st.info(
            f"Compacting {source_mb:.1f} MB in the background "
            f"({elapsed:.0f}s elapsed). AutoScan can keep running."
        )
        return

    if isinstance(job, dict) and job.get("status") == "failed":
        st.error(
            "Analysis bundle failed: "
            + str(job.get("error_type") or "Error")
            + " — "
            + str(job.get("error_message") or "unknown error")
        )
        return

    if isinstance(job, dict) and job.get("status") == "completed":
        result = job.get("result")
        if isinstance(result, dict):
            st.session_state[SESSION_KEY] = result

    info = st.session_state.get(SESSION_KEY)
    if not isinstance(info, dict):
        return

    filename = str(info.get("filename") or "")
    archive_path = STATIC_DIR / filename
    if not filename or not archive_path.exists():
        st.session_state.pop(SESSION_KEY, None)
        return

    def materialize_compact_bundle() -> bytes:
        return archive_path.read_bytes()

    st.download_button(
        label=(
            f"⬇ Download compact analysis bundle "
            f"({float(info.get('archive_bytes') or 0) / (1024 * 1024):.1f} MB)"
        ),
        data=materialize_compact_bundle,
        file_name=filename,
        mime="application/zip",
        key=f"walter-gs510-download-{filename}",
        on_click="ignore",
        width="stretch",
    )
    st.caption(
        f"{int(info.get('candidate_rows') or 0):,} candidate rows retained. "
        "Use this bundle for ChatGPT review; keep Full Session Backup only for archival."
    )


def render_compact_analysis_bundle_controls(
    candidate_history_path: str | Path,
    flight_recorder_path: str | Path,
) -> None:
    import streamlit as st

    candidate_path = Path(candidate_history_path)
    flight_path = Path(flight_recorder_path)
    fragment = getattr(st, "fragment", None)
    if not callable(fragment):
        _render(candidate_path, flight_path)
        return

    @fragment(run_every=JOB_POLL_SECONDS)
    def analysis_bundle_fragment() -> None:
        _render(candidate_path, flight_path)

    analysis_bundle_fragment()
