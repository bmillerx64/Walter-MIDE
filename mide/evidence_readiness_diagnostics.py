"""GS246 Diagnostics-only rendering for completed-scan evidence readiness."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mide.evidence_readiness import (
    STATUS_NOT_READY,
    STATUS_READY,
    STATUS_UNMEASURED,
    STATUS_WATCH,
    evidence_readiness_summary,
)


def render_evidence_readiness_diagnostics(ui: Any, report: Mapping[str, Any]) -> None:
    """Surface the snapshotted GS245 readiness verdict without recomputing it."""
    ui.subheader("Evidence Readiness Gate")
    ui.caption(evidence_readiness_summary(report))

    status = str(report.get("status") or STATUS_UNMEASURED)
    pct = report.get("trusted_pct")
    pct_text = "N/A" if pct is None else f"{float(pct):.1f}%"
    target = float(report.get("target_pct", 99.0) or 99.0)

    columns = ui.columns(4)
    columns[0].metric("Readiness", status)
    columns[1].metric("Evidence Reliability", pct_text)
    columns[2].metric("Reliability Target", f"{target:.1f}%")
    columns[3].metric("Candidates Audited", int(report.get("candidates_audited", 0) or 0))

    if status == STATUS_READY:
        ui.success("Evidence readiness target met for this completed scan.")
    elif status == STATUS_WATCH:
        ui.warning("Evidence is near target but does not yet meet the 99% readiness standard.")
    elif status == STATUS_NOT_READY:
        ui.error("Evidence is below Walter's readiness standard for this completed scan.")
    else:
        ui.info("Evidence readiness is unmeasured for this completed scan.")

    reasons = [str(reason) for reason in report.get("reasons", []) if reason]
    if reasons:
        ui.caption("Readiness evidence: " + " ".join(reasons))
    ui.caption(
        "Diagnostics only. This readiness verdict does not gate, rank, score, suppress, "
        "promote, alert, or execute candidates."
    )
