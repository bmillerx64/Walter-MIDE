"""Completed-scan market-evidence observation (GS243).

This module is deliberately downstream of Walter's decisions. It reads candidate
records, delegates evidence classification to GS241, and returns detached
diagnostics; it never gates, ranks, scores, or mutates a candidate.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from mide.market_evidence_audit import market_evidence_report
from mide.evidence_readiness_diagnostics import render_evidence_readiness_diagnostics


_ELEVATED_STATES = {
    "focus", "focused", "escalating", "strengthening", "entry ready",
    "entry-ready", "primary", "secondary",
}
_ELEVATED_FLAGS = (
    "entry_ready", "qualified_for_entry", "is_primary", "is_secondary",
    "primary", "secondary", "focus", "escalating", "strengthening",
)
_STATE_FIELDS = (
    "decision_state", "candidate_status", "escalation_state", "mission_role",
    "priority_tier", "status",
)


def _decision_state(candidate: Mapping[str, Any]) -> object | None:
    for field in _STATE_FIELDS:
        value = candidate.get(field)
        if value is not None and value != "":
            return value
    return None


def _is_elevated(candidate: Mapping[str, Any]) -> bool:
    """Recognize Walter's existing elevated treatment without deriving policy."""
    if any(candidate.get(field) is True for field in _ELEVATED_FLAGS):
        return True
    return any(
        str(candidate.get(field) or "").strip().lower().replace("_", " ")
        in _ELEVATED_STATES
        for field in _STATE_FIELDS
    )


def live_evidence_observation(
    candidates: Iterable[Mapping[str, Any]],
    *,
    scan_timestamp: datetime | str | None = None,
    max_age_seconds: float = 120.0,
) -> dict[str, object]:
    """Return a deterministic, read-only evidence aggregate for one scan."""
    observations: list[dict[str, object]] = []
    for candidate in candidates:
        evidence = market_evidence_report(
            candidate,
            scan_timestamp=scan_timestamp,
            max_age_seconds=max_age_seconds,
        )
        elevated = _is_elevated(candidate)
        observations.append({
            "symbol": evidence["symbol"],
            "evidence_status": evidence["status"],
            "trusted": evidence["trusted"],
            "completeness_pct": evidence["completeness_pct"],
            "fresh": evidence["fresh"],
            "source_bar_age_seconds": evidence["source_bar_age_seconds"],
            "missing_fields": list(evidence["missing_fields"]),
            "coherence_failures": list(evidence["coherence_failures"]),
            "elevated": elevated,
            "decision_state": _decision_state(candidate),
            "conviction": candidate.get("conviction", candidate.get("conviction_score")),
        })

    audited = len(observations)
    trusted = sum(row["evidence_status"] == "TRUSTED" for row in observations)
    caution = sum(row["evidence_status"] == "CAUTION" for row in observations)
    insufficient = sum(row["evidence_status"] == "INSUFFICIENT" for row in observations)
    mismatches = [
        str(row["symbol"]) for row in observations
        if row["elevated"] and row["evidence_status"] != "TRUSTED"
    ]
    return {
        "candidates_audited": audited,
        "trusted_count": trusted,
        "caution_count": caution,
        "insufficient_count": insufficient,
        "trusted_pct": round(trusted / audited * 100, 1) if audited else None,
        "stale_evidence_count": sum(not row["fresh"] for row in observations),
        "incomplete_evidence_count": sum(bool(row["missing_fields"]) for row in observations),
        "incoherent_evidence_count": sum(bool(row["coherence_failures"]) for row in observations),
        "nontrusted_elevated_count": len(mismatches),
        "nontrusted_elevated_symbols": mismatches,
        "observations": observations,
    }


live_evidence_report = live_evidence_observation


def live_evidence_summary(report: Mapping[str, Any]) -> str:
    """Format the compact operator summary for a completed-scan report."""
    pct = report.get("trusted_pct")
    pct_text = "N/A trusted" if pct is None else f"{float(pct):.0f}% trusted"
    mismatch_count = int(report.get("nontrusted_elevated_count", 0) or 0)
    mismatch_label = "mismatch" if mismatch_count == 1 else "mismatches"
    return (
        f"Evidence audit: {int(report.get('candidates_audited', 0) or 0)} candidates"
        f" · {int(report.get('trusted_count', 0) or 0)} TRUSTED"
        f" · {int(report.get('caution_count', 0) or 0)} CAUTION"
        f" · {int(report.get('insufficient_count', 0) or 0)} INSUFFICIENT"
        f" · {pct_text} · {mismatch_count} elevated {mismatch_label}"
    )


def render_live_evidence_diagnostics(ui: Any, report: Mapping[str, Any]) -> None:
    """Render the exact completed-scan evidence and stored readiness snapshot."""
    readiness = report.get("readiness_snapshot")
    if isinstance(readiness, Mapping):
        render_evidence_readiness_diagnostics(ui, readiness)
    else:
        ui.info("Evidence readiness snapshot unavailable for this completed scan.")
    ui.subheader("Live Evidence Reliability")
    ui.caption(live_evidence_summary(report))
    columns = ui.columns(5)
    pct = report.get("trusted_pct")
    columns[0].metric("Evidence Reliability %", "N/A" if pct is None else f"{float(pct):.1f}%")
    columns[1].metric("TRUSTED / CAUTION / INSUFFICIENT", (
        f"{report.get('trusted_count', 0)} / {report.get('caution_count', 0)} / "
        f"{report.get('insufficient_count', 0)}"
    ))
    columns[2].metric("Stale", report.get("stale_evidence_count", 0))
    columns[3].metric("Incomplete", report.get("incomplete_evidence_count", 0))
    columns[4].metric("Elevated mismatches", report.get("nontrusted_elevated_count", 0))
    mismatches = {
        row.get("symbol"): row for row in report.get("observations", [])
        if row.get("elevated") and row.get("evidence_status") != "TRUSTED"
    }
    for symbol in report.get("nontrusted_elevated_symbols", []):
        row = mismatches.get(symbol, {})
        reasons = []
        if not row.get("fresh", False):
            reasons.append("stale")
        if row.get("missing_fields"):
            reasons.append("missing " + ", ".join(row["missing_fields"]))
        if row.get("coherence_failures"):
            reasons.append("incoherent " + ", ".join(row["coherence_failures"]))
        ui.warning(f"{symbol}: {row.get('evidence_status', 'non-TRUSTED')} · " + ("; ".join(reasons) or "evidence not trusted"))
