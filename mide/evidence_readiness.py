"""GS244 read-only evidence readiness assessment.

Converts GS243 completed-scan evidence observations into a deterministic operator
readiness verdict. This module is diagnostic only: it never gates, ranks, scores,
suppresses, promotes, or mutates candidates.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

STATUS_READY = "READY"
STATUS_WATCH = "WATCH"
STATUS_NOT_READY = "NOT READY"
STATUS_UNMEASURED = "UNMEASURED"


def evidence_readiness_report(report: Mapping[str, Any]) -> dict[str, object]:
    """Assess whether the completed scan's evidence is reliable enough to trust."""
    audited = int(report.get("candidates_audited", 0) or 0)
    trusted_pct = report.get("trusted_pct")
    mismatches = int(report.get("nontrusted_elevated_count", 0) or 0)
    stale = int(report.get("stale_evidence_count", 0) or 0)
    incomplete = int(report.get("incomplete_evidence_count", 0) or 0)
    incoherent = int(report.get("incoherent_evidence_count", 0) or 0)

    reasons: list[str] = []
    if audited == 0 or trusted_pct is None:
        status = STATUS_UNMEASURED
        reasons.append("No candidate evidence was measured in this completed scan.")
    else:
        pct = float(trusted_pct)
        if mismatches:
            reasons.append(f"{mismatches} elevated candidate(s) had non-TRUSTED evidence.")
        if incoherent:
            reasons.append(f"{incoherent} candidate(s) had incoherent market evidence.")
        if stale:
            reasons.append(f"{stale} candidate(s) had stale market evidence.")
        if incomplete:
            reasons.append(f"{incomplete} candidate(s) had incomplete market evidence.")

        # Diagnostic readiness bands only. These do not participate in decisions.
        if pct >= 99.0 and mismatches == 0 and incoherent == 0:
            status = STATUS_READY
        elif pct >= 90.0 and mismatches == 0 and incoherent == 0:
            status = STATUS_WATCH
        else:
            status = STATUS_NOT_READY

        if not reasons and status == STATUS_READY:
            reasons.append("Evidence reliability meets the 99% target with no elevated mismatches or incoherence.")
        elif not reasons:
            reasons.append("Evidence reliability is below the 99% target.")

    return {
        "status": status,
        "candidates_audited": audited,
        "trusted_pct": trusted_pct,
        "target_pct": 99.0,
        "target_met": status == STATUS_READY,
        "nontrusted_elevated_count": mismatches,
        "stale_evidence_count": stale,
        "incomplete_evidence_count": incomplete,
        "incoherent_evidence_count": incoherent,
        "reasons": reasons,
    }


def evidence_readiness_summary(report: Mapping[str, Any]) -> str:
    result = evidence_readiness_report(report)
    pct = result["trusted_pct"]
    pct_text = "N/A" if pct is None else f"{float(pct):.1f}%"
    return f"Evidence readiness: {result['status']} · {pct_text} trusted · target 99%"
