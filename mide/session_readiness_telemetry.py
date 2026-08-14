"""GS249 read-only session evidence-readiness telemetry.

Aggregates the immutable GS248 readiness history without changing any live
scanner or decision behavior.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from mide.evidence_readiness import STATUS_NOT_READY, STATUS_READY, STATUS_UNMEASURED, STATUS_WATCH


def session_readiness_report(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize stored completed-scan readiness snapshots for this session."""
    counts = {STATUS_READY: 0, STATUS_WATCH: 0, STATUS_NOT_READY: 0, STATUS_UNMEASURED: 0}
    measured_pcts: list[float] = []
    total_candidates = 0
    total_elevated_mismatches = 0
    total_stale = 0
    total_incomplete = 0
    total_incoherent = 0

    for entry in history:
        snapshot = entry.get("readiness_snapshot")
        if not isinstance(snapshot, Mapping):
            snapshot = {}
        status = str(snapshot.get("status") or STATUS_UNMEASURED)
        if status not in counts:
            status = STATUS_UNMEASURED
        counts[status] += 1

        pct = snapshot.get("trusted_pct")
        if pct is not None:
            measured_pcts.append(float(pct))
        total_candidates += int(snapshot.get("candidates_audited", 0) or 0)
        total_elevated_mismatches += int(snapshot.get("nontrusted_elevated_count", 0) or 0)
        total_stale += int(snapshot.get("stale_evidence_count", 0) or 0)
        total_incomplete += int(snapshot.get("incomplete_evidence_count", 0) or 0)
        total_incoherent += int(snapshot.get("incoherent_evidence_count", 0) or 0)

    measured_scans = len(measured_pcts)
    ready_rate = round(counts[STATUS_READY] / measured_scans * 100, 1) if measured_scans else None
    average_reliability = round(sum(measured_pcts) / measured_scans, 1) if measured_scans else None
    target = 99.0

    return {
        "scans_recorded": len(history),
        "measured_scans": measured_scans,
        "unmeasured_scans": counts[STATUS_UNMEASURED],
        "ready_scans": counts[STATUS_READY],
        "watch_scans": counts[STATUS_WATCH],
        "not_ready_scans": counts[STATUS_NOT_READY],
        "ready_rate_pct": ready_rate,
        "average_reliability_pct": average_reliability,
        "target_pct": target,
        "session_target_met": bool(measured_scans and average_reliability is not None and average_reliability >= target and counts[STATUS_WATCH] == 0 and counts[STATUS_NOT_READY] == 0),
        "candidates_audited": total_candidates,
        "nontrusted_elevated_count": total_elevated_mismatches,
        "stale_evidence_count": total_stale,
        "incomplete_evidence_count": total_incomplete,
        "incoherent_evidence_count": total_incoherent,
    }


def render_session_readiness_diagnostics(ui: Any, report: Mapping[str, Any]) -> None:
    """Render longitudinal readiness telemetry in Diagnostics only."""
    ui.subheader("Session Evidence Reliability")
    columns = ui.columns(4)
    columns[0].metric("Measured Scans", int(report.get("measured_scans", 0) or 0))
    avg = report.get("average_reliability_pct")
    columns[1].metric("Avg Reliability", "N/A" if avg is None else f"{float(avg):.1f}%")
    ready_rate = report.get("ready_rate_pct")
    columns[2].metric("READY Rate", "N/A" if ready_rate is None else f"{float(ready_rate):.1f}%")
    columns[3].metric("Target", f"{float(report.get('target_pct', 99.0) or 99.0):.1f}%")

    measured = int(report.get("measured_scans", 0) or 0)
    if not measured:
        ui.info("Session evidence reliability is not yet measured.")
    elif report.get("session_target_met"):
        ui.success("Session evidence reliability is sustaining Walter's 99% target.")
    else:
        ui.warning("Session evidence reliability has not yet sustained Walter's 99% target across all measured scans.")

    ui.caption(
        f"READY {int(report.get('ready_scans', 0) or 0)} · "
        f"WATCH {int(report.get('watch_scans', 0) or 0)} · "
        f"NOT READY {int(report.get('not_ready_scans', 0) or 0)} · "
        f"UNMEASURED {int(report.get('unmeasured_scans', 0) or 0)} · "
        f"Candidates audited {int(report.get('candidates_audited', 0) or 0)}"
    )
    ui.caption(
        "Diagnostics only. Session telemetry summarizes stored completed-scan evidence and does not gate, rank, score, suppress, promote, alert, or execute candidates."
    )
