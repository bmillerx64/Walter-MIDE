"""Walter 3.0's staged decision engine.

This module consumes acquisition records; it intentionally does not fetch market data.
Every decision is represented as an ordered, serializable audit trail.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Iterable


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdentityPolicy:
    min_price: float = 0.05
    max_price: float = 5.0
    max_free_float: int = 3_500_000
    include_etfs: bool = False


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def _step(stage: int, category: str, result: str, *, passed=True, evidence=None):
    return {"stage": stage, "category": category, "result": result,
            "passed": passed, "evidence": list(evidence or [])}


def _free_float_lookup(record: dict) -> tuple[float | None, str | None, str | None]:
    """Return the normalized share count plus auditable lookup provenance."""
    for key in ("float_shares", "shares_float", "free_float"):
        shares = _number(record, key)
        if shares is not None:
            source = record.get("free_float_source") or record.get("float_source")
            return shares, str(source or f"record.{key} (provider unspecified)"), None
    millions = _number(record, "float_millions")
    if millions is not None:
        source = record.get("free_float_source") or record.get("float_source")
        return (
            millions * 1_000_000,
            str(source or "record.float_millions (provider unspecified)"),
            None,
        )
    return None, None, "No provider data"


def _log_free_float_diagnostic(
    symbol: str, price: float, shares: float | None, source: str | None,
    reason: str | None, policy: IdentityPolicy,
) -> None:
    """Emit one scan-friendly diagnostic for every symbol that passes Price."""
    lines = [f"Ticker: {symbol}", f"Price: PASS (${price:.2f})", "Free Float Lookup:"]
    if shares is None:
        lines.extend(["NULL", f"Reason: {reason or 'No provider data'}"])
    else:
        value = str(int(shares)) if shares.is_integer() else f"{shares:g}"
        lines.extend([f"Value Returned: {value}", f"Source: {source}"])
    lines.extend([
        f"Threshold: {policy.max_free_float}",
        f"Result: {'PASS' if shares is not None and shares <= policy.max_free_float else 'FAIL'}",
    ])
    logger.info("\n".join(lines))


def identity_decision(record: dict, policy: IdentityPolicy) -> tuple[bool, list[dict]]:
    """Apply Stage 2's non-negotiable filters in their mandated order."""
    audit: list[dict] = []
    symbol = str(record.get("symbol") or "").upper()
    asset_type = str(record.get("asset_type") or record.get("type") or "").lower()
    tradability_failure = next((reason for condition, reason in (
        (not record.get("tradable", True), "Non-tradable"),
        (bool(record.get("halted")), "Halted"),
        (bool(re.search(r"(?:\.|-)?W$", symbol)) or asset_type == "warrant", "Warrant"),
        (bool(re.search(r"(?:\.|-)?R$", symbol)) or asset_type == "right", "Right"),
        (bool(re.search(r"(?:\.|-)?U$", symbol)) or asset_type == "unit", "Unit"),
        (not policy.include_etfs and asset_type in {"etf", "fund"}, "ETF"),
        (str(record.get("exchange") or "").upper() == "OTC", "OTC"),
        (str(record.get("asset_status") or "active").lower() != "active", "Inactive symbol"),
    ) if condition), None)
    if tradability_failure:
        audit.append(_step(2, "Tradability", tradability_failure, passed=False))
        return False, audit
    audit.append(_step(2, "Tradability", "Passed"))

    price = _number(record, "price")
    if price is None or not policy.min_price <= price <= policy.max_price:
        actual = "Unavailable" if price is None else f"${price:.2f}"
        audit.append(_step(2, "Price", "Outside permitted range", passed=False,
                           evidence=[f"Actual: {actual}", f"Range: ${policy.min_price:.2f}–${policy.max_price:.2f}"]))
        return False, audit
    audit.append(_step(2, "Price", "Passed", evidence=[f"${price:.2f}"]))

    shares, float_source, lookup_reason = _free_float_lookup(record)
    _log_free_float_diagnostic(
        symbol, price, shares, float_source, lookup_reason, policy
    )
    if shares is None or shares > policy.max_free_float:
        actual = "Unavailable" if shares is None else f"{shares / 1_000_000:.2f}M"
        audit.append(_step(2, "Free Float", "Exceeds limit" if shares else "Unavailable",
                           passed=False, evidence=[f"Actual: {actual}", f"Limit: {policy.max_free_float / 1_000_000:.2f}M"]))
        return False, audit
    audit.append(_step(2, "Free Float", "Passed", evidence=[f"{shares / 1_000_000:.2f}M"]))
    return True, audit


def stage2_filter(records: Iterable[dict], policy: IdentityPolicy | None = None) -> tuple[list[dict], list[dict], dict]:
    """Apply the authoritative identity gate before any behavioral analysis.

    Rejections are returned as diagnostics, rather than candidates, so callers
    cannot accidentally score, display, or monitor a Stage 2 failure.
    """
    policy = policy or IdentityPolicy()
    accepted: list[dict] = []
    rejected: list[dict] = []
    counts = {
        "universe": 0,
        "tradability": 0,
        "price": 0,
        "free_float": 0,
        "free_float_evaluated": 0,
        "free_float_failed": 0,
        "free_float_lookup_failures": 0,
        "free_float_actual_failures": 0,
    }
    for source in records:
        counts["universe"] += 1
        passed, audit = identity_decision(source, policy)
        categories = {step["category"]: step["passed"] for step in audit}
        if categories.get("Tradability"):
            counts["tradability"] += 1
        if categories.get("Price"):
            counts["price"] += 1
            counts["free_float_evaluated"] += 1
        if categories.get("Free Float"):
            counts["free_float"] += 1
        if passed:
            accepted.append(dict(source))
            continue
        failure = audit[-1]
        diagnostic = {
            "symbol": str(source.get("symbol") or "").upper(),
            "decision": "Rejected",
            "stage": "Stage 2",
            "reason": failure["category"],
            "result": failure["result"],
            "evidence": list(failure.get("evidence") or []),
        }
        if failure["category"] == "Free Float":
            counts["free_float_failed"] += 1
            if failure["result"] == "Unavailable":
                counts["free_float_lookup_failures"] += 1
            else:
                counts["free_float_actual_failures"] += 1
            evidence = diagnostic["evidence"]
            diagnostic["free_float"] = evidence[0].removeprefix("Actual: ")
            diagnostic["maximum"] = evidence[1].removeprefix("Limit: ")
        rejected.append(diagnostic)
    counts["stage_3_analysis"] = len(accepted)
    return accepted, rejected, counts


def _band(value: float, bands: tuple[tuple[float, str], ...]) -> str:
    return next(label for threshold, label in bands if value >= threshold)


def _catalyst(record: dict) -> str:
    text = f"{record.get('headline', '')} {' '.join(record.get('discovery_reasons') or [])}".lower()
    for pattern, label in (("fda", "FDA"), ("earn", "Earnings"), ("8-k|10-k|10-q|sec filing", "SEC Filing"),
                           ("press release", "Press Release"), ("breaking", "Breaking News"), ("sympathy", "Sympathy")):
        if re.search(pattern, text):
            return label
    return "Unknown" if record.get("headline") else "No Catalyst"


def behavioral_decision(record: dict) -> tuple[bool, list[dict], int]:
    """Assess every category, then let confluence make the only advance decision."""
    audit: list[dict] = []
    participation = _number(record, "participation_surge_score", "participation_score") or 0
    participation_state = _band(participation, ((82, "Explosive"), (65, "Strong"), (40, "Building"), (0, "Weak")))
    acceleration_3m = _number(record, "volume_acceleration_3m")
    participation_reason = (
        "3-minute volume flattening"
        if acceleration_3m is not None and acceleration_3m <= 1
        else (
            f"3-minute volume expanding {acceleration_3m:.2f}×"
            if acceleration_3m is not None else "3-minute volume unavailable"
        )
    )
    audit.append(_step(3, "Participation", f"{participation:.0f} — {participation_reason}",
                       passed=participation_state != "Weak",
                       evidence=[f"State: {participation_state}",
                                 f"Dollar flow ${(_number(record, 'dollar_volume') or 0):,.0f}"]))
    audit.append(_step(3, "Catalyst", _catalyst(record), evidence=[record.get("headline")] if record.get("headline") else []))

    structure_score = _number(record, "structure_score")
    if structure_score is None:
        structure_score = 25 * sum(bool(record.get(k)) for k in ("higher_highs", "higher_lows", "healthy_pullbacks", "base_quality"))
    structure = _band(structure_score, ((80, "Excellent"), (60, "Healthy"), (35, "Developing"), (0, "Weak")))
    audit.append(_step(3, "Price Structure", structure, passed=structure != "Weak",
                       evidence=["Higher lows" if record.get("higher_lows") else "Higher lows not confirmed"]))

    distance = _number(record, "vwap_distance_pct") or 0
    relation = str(record.get("vwap_relation") or "").lower()
    vwap = "Reclaimed" if record.get("vwap_reclaimed_last_10m") else ("Holding" if relation == "above" else ("Testing" if relation == "testing" or abs(distance) <= 0.5 else ("Failing" if distance < -2 else "Below")))
    audit.append(_step(3, "VWAP", vwap, passed=vwap in {"Testing", "Reclaimed", "Holding"}, evidence=[f"Distance {distance:+.2f}%"]))

    st_distance = _number(record, "supertrend_distance_pct")
    if record.get("supertrend_flip") or record.get("supertrend_flipped_last_10m"):
        st = "Fresh Flip"
    elif record.get("supertrend_bullish"):
        st = "Holding Flip"
    elif st_distance is not None and st_distance <= 1:
        st = "Converging"
    else:
        st = "Failure"
    audit.append(_step(3, "SuperTrend", st, passed=st != "Failure", evidence=[f"Distance {st_distance:.2f}%"] if st_distance is not None else []))

    momentum_score = _number(record, "momentum_quality_score", "current_momentum", "opportunity_score") or 0
    acceleration = _number(record, "volume_acceleration", "acceleration_ratio") or 0
    momentum = "Exhausted" if record.get("exhaustion") else _band(momentum_score, ((80, "Powerful"), (60, "Strong"), (40, "Building"), (0, "Weak")))
    audit.append(_step(3, "Momentum Quality", momentum, passed=momentum not in {"Weak", "Exhausted"}, evidence=[f"Acceleration {acceleration:.2f}×"]))

    # Catalyst is deliberately excluded: it supports a thesis but is not mandatory.
    decision_steps = [audit[i] for i in (0, 2, 3, 4, 5)]
    agreement = sum(step["passed"] for step in decision_steps)
    confluence = (0, 20, 45, 65, 82, 100)[agreement]
    audit.append(_step(3, "Confluence", str(confluence), passed=agreement >= 3,
                       evidence=[f"{agreement}/5 independent evidence categories agree", "Catalyst not required or scored"]))
    # A weak category is evidence against the setup, never a veto.  Confluence is
    # the sole Stage 3 authority and advances any setup with three agreeing inputs.
    return agreement >= 3, audit, confluence


def evaluate(records: Iterable[dict], policy: IdentityPolicy | None = None) -> list[dict]:
    """Return records enriched with Stage 1–3 decisions and complete audit trails."""
    records = list(records)
    policy = policy or IdentityPolicy()
    output = []
    universe_size = len(records)
    for source in records:
        record = dict(source)
        audit = [_step(1, "Universe", "Discovered", evidence=[f"Universe size: {universe_size}"])]
        eligible, identity = identity_decision(record, policy)
        audit.extend(identity)
        if not eligible:
            decision, current_stage, confluence = "Rejected", "Stage 2", None
        else:
            advanced, behavior, confluence = behavioral_decision(record)
            audit.extend(behavior)
            decision, current_stage = ("Attention Earned", "Stage 4") if advanced else ("Rejected", "Stage 3")
        failed_step = next((step for step in reversed(audit) if not step["passed"]), None)
        record.update(decision_funnel=audit, universe_size=universe_size,
                      eligible=eligible, current_stage=current_stage,
                      final_decision=decision, confluence_score=confluence,
                      decision_engine_version="3.0",
                      rejection_reason=(
                          f"{failed_step['category']}: {failed_step['result']}"
                          if decision == "Rejected" and failed_step else None
                      ),
                      scanner_version="Decision Funnel 3.0",
                      candidate_status=(record.get("candidate_status", "Entry Ready") if decision == "Attention Earned" else "Removed"),
                      status=(record.get("status", "WATCH NOW") if decision == "Attention Earned" else "PASS"))
        output.append(record)
    return output
