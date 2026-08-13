"""Read-only evidence-completeness diagnostics for Walter candidates.

GS239 measures whether a displayed candidate has enough recorded evidence to support
Walter's explanation. It never changes qualification, ranking, thresholds, scoring,
entry readiness, alerts, or execution behavior.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


REQUIRED_STAGES = (
    "Catalyst Assessment",
    "Participation Assessment",
    "Expansion Assessment",
    "Mission Ranking and Publication",
)

RANKING_EVIDENCE_FIELDS = (
    "conviction",
    "participation",
    "expansion",
    "volume_expansion",
)


def _latest_stage(record: Mapping[str, object], stage: str) -> Mapping[str, object] | None:
    entries = record.get("architecture_audit") or []
    return next(
        (
            entry
            for entry in reversed(entries)
            if isinstance(entry, Mapping) and entry.get("stage") == stage
        ),
        None,
    )


def _latest_ranking(record: Mapping[str, object]) -> Mapping[str, object]:
    history = record.get("ranking_history") or []
    if not isinstance(history, Sequence) or not history:
        return {}
    latest = history[-1]
    return latest if isinstance(latest, Mapping) else {}


def candidate_evidence_report(record: Mapping[str, object]) -> dict[str, object]:
    """Return a deterministic, display-only audit of recorded candidate evidence."""
    symbol = str(record.get("symbol") or "").upper()
    missing_stages = [stage for stage in REQUIRED_STAGES if _latest_stage(record, stage) is None]

    ranking = _latest_ranking(record)
    ranking_evidence = ranking.get("evidence") or {}
    if not isinstance(ranking_evidence, Mapping):
        ranking_evidence = {}
    missing_ranking_fields = [
        field for field in RANKING_EVIDENCE_FIELDS if ranking_evidence.get(field) is None
    ]

    terminal_reason_present = bool(str(record.get("terminal_reason") or "").strip())
    ranking_present = bool(ranking)
    rank_present = ranking.get("rank") is not None if ranking_present else False
    qualified_present = "qualified" in ranking if ranking_present else False

    total_checks = len(REQUIRED_STAGES) + len(RANKING_EVIDENCE_FIELDS) + 3
    passed_checks = (
        len(REQUIRED_STAGES) - len(missing_stages)
        + len(RANKING_EVIDENCE_FIELDS) - len(missing_ranking_fields)
        + int(ranking_present)
        + int(rank_present)
        + int(qualified_present)
    )
    completeness_pct = round(passed_checks / total_checks * 100, 1)

    issues: list[str] = []
    if missing_stages:
        issues.append("missing architecture stage evidence: " + ", ".join(missing_stages))
    if not ranking_present:
        issues.append("missing ranking history")
    elif missing_ranking_fields:
        issues.append("missing ranking evidence: " + ", ".join(missing_ranking_fields))
    if ranking_present and not rank_present:
        issues.append("latest ranking has no rank")
    if ranking_present and not qualified_present:
        issues.append("latest ranking has no qualified flag")

    if completeness_pct >= 99:
        status = "COMPLETE"
    elif completeness_pct >= 80:
        status = "PARTIAL"
    else:
        status = "INSUFFICIENT"

    return {
        "symbol": symbol,
        "status": status,
        "completeness_pct": completeness_pct,
        "missing_stages": missing_stages,
        "missing_ranking_fields": missing_ranking_fields,
        "ranking_present": ranking_present,
        "rank_present": rank_present,
        "qualified_present": qualified_present,
        "terminal_reason_present": terminal_reason_present,
        "issues": issues,
        "evidence_complete": status == "COMPLETE",
    }


def candidate_evidence_summary(record: Mapping[str, object]) -> str:
    """Create a concise UI/narrative label without changing the underlying record."""
    report = candidate_evidence_report(record)
    return (
        f"Evidence {report['status']} · {report['completeness_pct']:.0f}%"
        if report["status"] != "COMPLETE"
        else "Evidence COMPLETE · 100%"
    )
