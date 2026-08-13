"""Additive Walter 2.0 opportunity scoring and explanations.

This module deliberately consumes scanner output rather than participating in
qualification. It must never be used as a workflow or alert predicate.
"""

from __future__ import annotations

import math

COMPONENT_WEIGHTS = {
    "participation": 25.0,
    "trend": 20.0,
    "structure": 20.0,
    "trigger": 15.0,
    "liquidity": 10.0,
    "catalyst": 10.0,
}

WORKFLOW_LABELS = {
    "New": "Watching",
    "Emerging": "Developing",
    "Watching": "Watching",
    "Strengthening": "Strengthening",
    "Entry Ready": "Entry Ready",
    "Weakening": "Watching",
    "Removed": "Watching",
}

LIFECYCLE_LABELS = {
    "Emerging": "Building Base",
    "Momentum": "Trending",
    "Distribution": "Exhausting",
    "Broken": "Breaking Down",
}


def _number(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def _points(quality: float, maximum: float) -> float:
    return max(0.0, min(maximum, quality * maximum / 100.0))


def dollar_flow_score(record: dict) -> float:
    """Return ranking-only dollar-flow evidence on a bounded logarithmic scale.

    The scanner already supplies dollar_volume. Converting it to a bounded score
    lets Mission Control distinguish genuinely active tape from thin names without
    changing qualification, workflow state, or entry readiness.
    """
    dollars = max(0.0, _number(record, "dollar_volume"))
    if dollars <= 0:
        return 0.0
    # $100k is the neutral floor. Each 10x increase adds 25 points, so roughly
    # $1M/$10M/$100M map to 25/50/75 while remaining bounded at 100.
    return round(max(0.0, min(100.0, 25.0 * math.log10(dollars / 100_000.0))), 1)


def opportunity_status(score: float) -> str:
    if score >= 90:
        return "Prime Opportunity"
    if score >= 75:
        return "Entry Candidate"
    if score >= 60:
        return "Strengthening"
    if score >= 40:
        return "Developing"
    return "Watching"


def workflow_label(record: dict) -> str:
    """Return presentation wording for today's scanner decision."""
    state = str(record.get("candidate_status") or record.get("status") or "Watching")
    return WORKFLOW_LABELS.get(state, state)


def lifecycle_label(record: dict) -> str:
    """Translate the persistent chart phase without exposing contradictory jargon."""
    phase = str(record.get("market_phase") or "Emerging")
    if phase == "Broken" and (
        record.get("vwap_relation") in {"above", "testing"}
        or record.get("supertrend_bullish")
        or _number(record, "volume_acceleration", 1) >= 1.0
    ):
        return "Recovering"
    if phase == "Momentum" and _number(record, "volume_acceleration", 1) >= 1.5:
        return "Accelerating"
    return LIFECYCLE_LABELS.get(phase, "Building Base")


def _decision_support(record: dict, strengths: list[str], blockers: list[str]) -> dict:
    """Build additive coaching copy; never participates in scanner decisions."""
    state = workflow_label(record)
    reasons = list(
        dict.fromkeys(
            [str(item) for item in record.get("promotion_condition_changes") or []]
            + strengths
            + [str(item) for item in record.get("reasons") or []]
        )
    )[:5]
    if not reasons:
        reasons = ["Qualified participation and price structure"]

    if state == "Entry Ready":
        blockers = []
    elif not blockers:
        trigger_reasons = (record.get("trigger_diagnostics") or {}).get("reasons") or []
        blockers = [str(trigger_reasons[0])] if trigger_reasons else ["Waiting for entry confirmation"]
    blockers = list(dict.fromkeys(blockers))[:3]

    extension = _number(record, "vwap_distance_pct")
    participation_strong = max(
        _number(record, "participation_score"),
        _number(record, "participation_surge_score"),
    ) >= 60
    if state == "Entry Ready":
        tradeability = "Buyable"
        tradeability_reason = "Entry conditions are confirmed"
        next_event = "If price structure or participation weakens, Walter will demote this setup."
    elif extension > 2 and record.get("vwap_relation") == "above":
        tradeability = "Don't Chase"
        tradeability_reason = f"{extension:.1f}% above VWAP"
        next_event = "If price pulls back toward VWAP while participation remains strong, Walter can promote this to Entry Ready."
    else:
        tradeability = "Wait"
        tradeability_reason = blockers[0]
        next_event = (
            f"If {blockers[0].lower()} resolves while participation remains strong, Walter can promote this further."
            if blockers else "If entry conditions confirm, Walter can promote this to Entry Ready."
        )
    if not participation_strong and state != "Entry Ready":
        next_event += " If participation weakens further, Walter will demote it."

    take_parts = [
        "Participation is strong." if participation_strong else "Participation still needs confirmation.",
        "The trend is healthy." if record.get("supertrend_bullish") else "Trend confirmation is incomplete.",
        (
            "Do not chase; wait for a pullback toward VWAP."
            if tradeability == "Don't Chase"
            else "The setup is buyable under Walter's current rules."
            if tradeability == "Buyable"
            else f"Wait: {tradeability_reason}."
        ),
    ]
    return {
        "workflow_label": state,
        "lifecycle_label": lifecycle_label(record),
        "promotion_reasons": reasons,
        "entry_blockers_explained": blockers,
        "next_event_explanation": next_event,
        "tradeability": tradeability,
        "tradeability_reason": tradeability_reason,
        "walter_take": " ".join(take_parts),
    }


def calculate_opportunity(record: dict) -> dict:
    """Return a deterministic, bounded score without changing scanner state."""
    participation_quality = max(
        _number(record, "participation_score"),
        _number(record, "participation_surge_score"),
    )

    confirmations = min(4.0, _number(record, "timeframe_confirmations"))
    trend_quality = (
        (35 if record.get("supertrend_bullish") else 0)
        + (25 if record.get("ema65_relation") == "above" else 0)
        + confirmations * 10
    )

    structure_quality = (
        (35 if record.get("vwap_relation") == "above" else 20 if record.get("vwap_relation") == "testing" else 0)
        + (25 if record.get("higher_lows") else 0)
        + (15 if record.get("near_hod") else 0)
        + (25 if record.get("ema65_relation") == "above" else 10 if _number(record, "ema65_distance_pct", 99) <= 1.5 else 0)
    )
    extension = max(0.0, _number(record, "vwap_distance_pct"))
    if record.get("vwap_relation") == "above" and extension > 2.0:
        structure_quality -= min(50.0, (extension - 2.0) * 10.0 + 15.0)

    trigger = record.get("trigger_diagnostics") or {}
    checks = trigger.get("checks") or []
    if checks:
        trigger_quality = 100.0 * sum(bool(c.get("passed")) for c in checks) / len(checks)
    else:
        trigger_quality = 100.0 if record.get("trigger") == "YES" else (70.0 if record.get("supertrend_flip") else 30.0)

    spread = _number(record, "spread_pct", 10)
    dollars = _number(record, "dollar_volume")
    liquidity_quality = max(0.0, 100.0 - spread * 12.0)
    if dollars < 100_000:
        liquidity_quality -= 45
    elif dollars < 500_000:
        liquidity_quality -= 20

    if record.get("headline"):
        catalyst_quality = 70.0 + max(-50.0, min(30.0, _number(record, "catalyst_score") * 2.0))
        age = record.get("news_age_hours")
        if age is not None:
            catalyst_quality -= min(35.0, max(0.0, _number(record, "news_age_hours") - 3.0) * 0.6)
    else:
        catalyst_quality = 20.0

    qualities = {
        "participation": participation_quality,
        "trend": trend_quality,
        "structure": structure_quality,
        "trigger": trigger_quality,
        "liquidity": liquidity_quality,
        "catalyst": catalyst_quality,
    }
    breakdown = {
        name: round(_points(qualities[name], maximum), 1)
        for name, maximum in COMPONENT_WEIGHTS.items()
    }
    score = round(max(0.0, min(100.0, sum(breakdown.values()))), 1)

    strengths: list[tuple[float, str]] = []
    if participation_quality >= 75:
        strengths.append((participation_quality, "Explosive participation"))
    elif participation_quality >= 50:
        strengths.append((participation_quality, "Strong participation"))
    if confirmations >= 3 or (record.get("supertrend_bullish") and record.get("ema65_relation") == "above"):
        strengths.append((trend_quality, "Multi-timeframe trend alignment"))
    if record.get("vwap_relation") == "above":
        strengths.append((structure_quality, "Above VWAP" if not record.get("supertrend_flip") else "Fresh VWAP/trend reclaim"))
    if trigger_quality >= 80:
        strengths.append((trigger_quality, "Trigger ready"))
    if liquidity_quality >= 80:
        strengths.append((liquidity_quality, "Tradeable liquidity"))
    if catalyst_quality >= 70:
        strengths.append((catalyst_quality, "Confirmed catalyst"))

    blockers: list[tuple[float, str]] = []
    if extension > 2.0 and record.get("vwap_relation") == "above":
        blockers.append((100 + extension, f"Extended {extension:.1f}% above VWAP — wait for pullback"))
    if trigger_quality < 80:
        reason = (trigger.get("reasons") or ["Trigger not ready"])[0]
        blockers.append((100 - trigger_quality, str(reason)))
    if spread > 3:
        blockers.append((spread * 5, f"Spread elevated at {spread:.1f}%"))
    if not record.get("headline"):
        blockers.append((25, "No confirmed catalyst"))
    if record.get("vwap_relation") == "below":
        blockers.append((40, "Below VWAP"))

    strengths.sort(key=lambda item: (-item[0], item[1]))
    blockers.sort(key=lambda item: (-item[0], item[1]))
    result = {
        "opportunity_score_v2": score,
        "opportunity_status": opportunity_status(score),
        "opportunity_breakdown": breakdown,
        "opportunity_strengths": [text for _, text in strengths[:3]],
        "opportunity_blockers": [text for _, text in blockers[:3]],
    }
    result.update(_decision_support(record, result["opportunity_strengths"], result["opportunity_blockers"]))
    return result


def enrich_opportunity(record: dict) -> dict:
    # Ranking-only evidence. Preserve an upstream score if a future data source
    # supplies one; otherwise derive it from the scanner's observed dollar volume.
    if record.get("dollar_flow_score") is None:
        record["dollar_flow_score"] = dollar_flow_score(record)
    record.update(calculate_opportunity(record))
    return record
