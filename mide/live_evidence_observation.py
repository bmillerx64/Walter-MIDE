"""Completed-scan market-evidence observation (GS243)."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any
from mide.market_evidence_audit import market_evidence_report
from mide.evidence_readiness import evidence_readiness_report
from mide.evidence_readiness_diagnostics import render_evidence_readiness_diagnostics

_ELEVATED_STATES = {"focus", "focused", "escalating", "strengthening", "entry ready", "entry-ready", "primary", "secondary"}
_ELEVATED_FLAGS = ("entry_ready", "qualified_for_entry", "is_primary", "is_secondary", "primary", "secondary", "focus", "escalating", "strengthening")
_STATE_FIELDS = ("decision_state", "candidate_status", "escalation_state", "mission_role", "priority_tier", "status")

def _decision_state(candidate: Mapping[str, Any]) -> object | None:
    for field in _STATE_FIELDS:
        value = candidate.get(field)
        if value is not None and value != "": return value
    return None

def _is_elevated(candidate: Mapping[str, Any]) -> bool:
    if any(candidate.get(field) is True for field in _ELEVATED_FLAGS): return True
    return any(str(candidate.get(field) or "").strip().lower().replace("_", " ") in _ELEVATED_STATES for field in _STATE_FIELDS)

def live_evidence_observation(candidates: Iterable[Mapping[str, Any]], *, scan_timestamp: datetime | str | None = None, max_age_seconds: float = 120.0) -> dict[str, object]:
    observations=[]
    for candidate in candidates:
        evidence=market_evidence_report(candidate, scan_timestamp=scan_timestamp, max_age_seconds=max_age_seconds)
        elevated=_is_elevated(candidate)
        observations.append({"symbol":evidence["symbol"],"evidence_status":evidence["status"],"trusted":evidence["trusted"],"completeness_pct":evidence["completeness_pct"],"fresh":evidence["fresh"],"source_bar_age_seconds":evidence["source_bar_age_seconds"],"missing_fields":list(evidence["missing_fields"]),"coherence_failures":list(evidence["coherence_failures"]),"elevated":elevated,"decision_state":_decision_state(candidate),"conviction":candidate.get("conviction",candidate.get("conviction_score"))})
    audited=len(observations); trusted=sum(r["evidence_status"]=="TRUSTED" for r in observations); caution=sum(r["evidence_status"]=="CAUTION" for r in observations); insufficient=sum(r["evidence_status"]=="INSUFFICIENT" for r in observations)
    mismatches=[str(r["symbol"]) for r in observations if r["elevated"] and r["evidence_status"]!="TRUSTED"]
    return {"candidates_audited":audited,"trusted_count":trusted,"caution_count":caution,"insufficient_count":insufficient,"trusted_pct":round(trusted/audited*100,1) if audited else None,"stale_evidence_count":sum(not r["fresh"] for r in observations),"incomplete_evidence_count":sum(bool(r["missing_fields"]) for r in observations),"incoherent_evidence_count":sum(bool(r["coherence_failures"]) for r in observations),"nontrusted_elevated_count":len(mismatches),"nontrusted_elevated_symbols":mismatches,"observations":observations}

live_evidence_report=live_evidence_observation

def live_evidence_summary(report: Mapping[str, Any]) -> str:
    pct=report.get("trusted_pct"); pct_text="N/A trusted" if pct is None else f"{float(pct):.0f}% trusted"; n=int(report.get("nontrusted_elevated_count",0) or 0)
    return f"Evidence audit: {int(report.get('candidates_audited',0) or 0)} candidates · {int(report.get('trusted_count',0) or 0)} TRUSTED · {int(report.get('caution_count',0) or 0)} CAUTION · {int(report.get('insufficient_count',0) or 0)} INSUFFICIENT · {pct_text} · {n} elevated {'mismatch' if n==1 else 'mismatches'}"

def render_live_evidence_diagnostics(ui: Any, report: Mapping[str, Any], *, readiness_report: Mapping[str, Any] | None=None) -> None:
    """Render the exact completed-scan readiness snapshot when available."""
    readiness = readiness_report or report.get("readiness_snapshot") or evidence_readiness_report(report)
    render_evidence_readiness_diagnostics(ui, readiness)
    ui.subheader("Live Evidence Reliability"); ui.caption(live_evidence_summary(report)); columns=ui.columns(5); pct=report.get("trusted_pct")
    columns[0].metric("Evidence Reliability %","N/A" if pct is None else f"{float(pct):.1f}%")
    columns[1].metric("TRUSTED / CAUTION / INSUFFICIENT",f"{report.get('trusted_count',0)} / {report.get('caution_count',0)} / {report.get('insufficient_count',0)}")
    columns[2].metric("Stale",report.get("stale_evidence_count",0)); columns[3].metric("Incomplete",report.get("incomplete_evidence_count",0)); columns[4].metric("Elevated mismatches",report.get("nontrusted_elevated_count",0))
    mismatches={r.get("symbol"):r for r in report.get("observations",[]) if r.get("elevated") and r.get("evidence_status")!="TRUSTED"}
    for symbol in report.get("nontrusted_elevated_symbols",[]):
        row=mismatches.get(symbol,{}); reasons=[]
        if not row.get("fresh",False): reasons.append("stale")
        if row.get("missing_fields"): reasons.append("missing "+", ".join(row["missing_fields"]))
        if row.get("coherence_failures"): reasons.append("incoherent "+", ".join(row["coherence_failures"]))
        ui.warning(f"{symbol}: {row.get('evidence_status','non-TRUSTED')} · "+("; ".join(reasons) or "evidence not trusted"))
