"""Evidence-bound explanations for Walter Mission decisions.

This module deliberately reads only the architecture audit and ranking history.  It
does not inspect arbitrary scanner fields, so presentation code cannot accidentally
turn an unrecorded heuristic into an explanation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from mide.candidate_evidence import candidate_evidence_report, candidate_evidence_summary


ASSESSMENT_STAGES = (
    "Catalyst Assessment",
    "Participation Assessment",
    "Expansion Assessment",
)


def _latest_audit(record: Mapping[str, object], stage: str) -> Mapping[str, object] | None:
    entries = record.get("architecture_audit") or []
    return next((entry for entry in reversed(entries) if entry.get("stage") == stage), None)


def _stage_summary(record: Mapping[str, object], stage: str) -> str:
    entry = _latest_audit(record, stage)
    if not entry:
        return "No recorded stage evidence."
    reason = str(entry.get("reason") or "No recorded reason.")
    return f"{entry.get('decision', 'Not evaluated')}: {reason}"


def _latest_ranking(record: Mapping[str, object]) -> Mapping[str, object]:
    history = record.get("ranking_history") or []
    return history[-1] if history else {}


def _entry_summary(evidence: Mapping[str, object]) -> tuple[str, str]:
    if evidence.get("entry_readiness"):
        return "Entry ready according to recorded ranking evidence.", "Entry readiness is withdrawn."
    missing = []
    if not evidence.get("vwap_reclaimed"):
        missing.append("a VWAP reclaim")
    if not evidence.get("supertrend_bullish"):
        missing.append("bullish SuperTrend confirmation")
    if float(evidence.get("participation") or 0) <= 90:
        missing.append("participation above 90")
    if missing:
        joined = ", ".join(missing[:-1]) + (" and " if len(missing) > 1 else "") + missing[-1]
        return f"Not entry ready; recorded ranking evidence is missing {joined}.", f"Recorded evidence confirms {joined}."
    return "Not entry ready in the recorded ranking evidence.", "Entry readiness becomes true in recorded ranking evidence."


def _factor_lines(record: Mapping[str, object]) -> tuple[list[str], list[str]]:
    positives, negatives = [], []
    for stage in ASSESSMENT_STAGES:
        entry = _latest_audit(record, stage)
        if not entry:
            continue
        text = f"{stage}: {entry.get('reason') or 'No recorded reason.'}"
        (positives if entry.get("decision") in {"Qualified", "Qualified and Ranked"} else negatives).append(text)
    return positives, negatives


def _outrank_reason(record: Mapping[str, object], lower: Mapping[str, object] | None) -> str:
    if not lower:
        return "No lower-ranked Mission candidate is recorded."
    own = _latest_ranking(record).get("evidence") or {}
    other = _latest_ranking(lower).get("evidence") or {}
    labels = (
        ("conviction", "conviction"),
        ("participation", "participation"),
        ("expansion", "expansion"),
        ("volume_expansion", "volume expansion"),
    )
    advantages = [label for key, label in labels if float(own.get(key) or 0) > float(other.get(key) or 0)]
    if advantages:
        return f"It outranked {lower.get('symbol')} with stronger recorded " + ", ".join(advantages) + "."
    return f"The recorded ranker placed it above {lower.get('symbol')}; no stronger component is present in the ranking snapshot."


def _why_not_one(record: Mapping[str, object], primary: Mapping[str, object] | None) -> str | None:
    if not primary or record is primary:
        return None
    own = _latest_ranking(record).get("evidence") or {}
    top = _latest_ranking(primary).get("evidence") or {}
    gaps = []
    for key, label in (("conviction", "conviction"), ("participation", "participation"), ("expansion", "expansion")):
        if float(own.get(key) or 0) < float(top.get(key) or 0):
            gaps.append(label)
    if gaps:
        return f"Why Not #1? {primary.get('symbol')} has stronger recorded " + ", ".join(gaps) + "."
    return f"Why Not #1? The recorded Mission rank places {primary.get('symbol')} first; no lower component is recorded."


def build_decision_narrative(
    record: Mapping[str, object], *, lower: Mapping[str, object] | None = None,
    primary: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a concise explanation whose claims are traceable to ledger entries."""
    ranking = _latest_ranking(record)
    evidence = ranking.get("evidence") or {}
    positives, negatives = _factor_lines(record)
    readiness, upgrade = _entry_summary(evidence)
    evidence_report = candidate_evidence_report(record)
    qualified = _latest_audit(record, "Mission Ranking and Publication")
    qualification = (
        str(qualified.get("reason")) if qualified
        else str(record.get("terminal_reason") or "No recorded qualification reason.")
    )
    removal = None
    if ranking and not ranking.get("qualified"):
        removal = f"Why Removed? {record.get('terminal_reason') or 'The latest ledger scan no longer qualifies the candidate.'}"
    movement = list(ranking.get("reasons") or [])
    rank_change = None
    if ranking.get("previous_rank") != ranking.get("rank"):
        reason = ", ".join(movement) if movement else "no component change was recorded"
        rank_change = f"Rank changed from {ranking.get('previous_rank')} to {ranking.get('rank')}: {reason}."
    narrative = f"Qualified because {qualification}. {_outrank_reason(record, lower)} {readiness} Upgrade: {upgrade}"
    return {
        "decision_narrative": narrative,
        "strongest_positive_factors": positives[:3],
        "strongest_negative_factors": negatives[:3],
        "catalyst_summary": _stage_summary(record, "Catalyst Assessment"),
        "participation_summary": _stage_summary(record, "Participation Assessment"),
        "expansion_summary": _stage_summary(record, "Expansion Assessment"),
        "conviction_trend": f"{ranking.get('conviction_trend', '→')} ({float(ranking.get('conviction_change') or 0):+g})",
        "entry_readiness_summary": readiness,
        "upgrade_event": upgrade,
        "removal_event": "A recorded architecture stage rejects the candidate or it leaves the live universe.",
        "why_not_number_one": _why_not_one(record, primary),
        "ranking_change_explanation": rank_change,
        "why_removed": removal,
        "evidence_source": "architecture_audit and ranking_history",
        "evidence_trust": evidence_report,
        "evidence_trust_summary": candidate_evidence_summary(record),
    }


def attach_decision_narratives(records: Sequence[dict]) -> None:
    """Attach explanations to every ledger record after the live ranking is final."""
    ranked = sorted(
        (r for r in records if r.get("mission_rank") is not None),
        key=lambda r: int(r["mission_rank"]),
    )
    primary = ranked[0] if ranked else None
    lower_by_symbol = {r.get("symbol"): ranked[i + 1] if i + 1 < len(ranked) else None for i, r in enumerate(ranked)}
    for record in records:
        record["decision_explanation"] = build_decision_narrative(
            record, lower=lower_by_symbol.get(record.get("symbol")), primary=primary
        )
