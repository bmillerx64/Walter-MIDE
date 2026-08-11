"""Live-market safety overlays for Walter's squeeze-oriented workflow.

These guards are intentionally narrow: they keep stale share-structure data and
low-participation names from being promoted while preserving genuine early
ignitions that are accelerating across multiple short windows.
"""

from __future__ import annotations

from typing import Any

from . import decision_engine
from .free_float import YahooFinanceFloatProvider


_ORIGINAL_YAHOO_PARSE = YahooFinanceFloatProvider.parse
_ORIGINAL_BEHAVIORAL_DECISION = decision_engine.behavioral_decision


def _positive_number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("raw")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _conservative_yahoo_share_structure(payload: object) -> float | None:
    """Use the larger of Yahoo float and shares outstanding for the squeeze gate.

    Webull Desktop can show a newly enlarged float before third-party float fields
    catch up. Shares outstanding is therefore used as a conservative conflict
    ceiling: Walter may miss a borderline low-float name, but it cannot promote a
    clearly enlarged capital structure as a <=3.5M squeeze candidate.
    """
    float_shares = _ORIGINAL_YAHOO_PARSE(payload)
    outstanding = None
    if isinstance(payload, dict):
        summary = payload.get("quoteSummary")
        results = summary.get("result") if isinstance(summary, dict) else None
        statistics = results[0].get("defaultKeyStatistics") if results else None
        if isinstance(statistics, dict):
            outstanding = _positive_number(statistics.get("sharesOutstanding"))
    values = [value for value in (float_shares, outstanding) if value is not None]
    return max(values) if values else None


def _number(record: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        try:
            value = record.get(key)
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    return default


def _participation_floor(record: dict) -> tuple[bool, str]:
    """Require real session participation or unmistakable multi-window ignition."""
    rvol = _number(record, "rvol_proxy", "rvol", "relative_volume", default=0.0)
    volume_1m = _number(record, "volume_acceleration_1m", "volume_acceleration", default=0.0)
    volume_3m = _number(record, "volume_acceleration_3m", "volume_acceleration", default=0.0)
    dollar_1m = _number(record, "dollar_flow_acceleration_1m", default=0.0)
    dollar_3m = _number(record, "dollar_flow_acceleration_3m", default=0.0)

    if rvol >= 1.0:
        return True, f"RVOL {rvol:.2f}x"

    ignition = (
        volume_1m >= 2.0
        and volume_3m >= 1.5
        and max(dollar_1m, dollar_3m) >= 1.5
    )
    if ignition:
        return True, (
            f"Early ignition override: RVOL {rvol:.2f}x, "
            f"volume {volume_1m:.2f}x/{volume_3m:.2f}x"
        )
    return False, (
        f"Participation too thin: RVOL {rvol:.2f}x; "
        f"volume acceleration {volume_1m:.2f}x/{volume_3m:.2f}x"
    )


def _behavioral_decision_with_participation_floor(record: dict):
    advanced, audit, confluence = _ORIGINAL_BEHAVIORAL_DECISION(record)
    floor_passed, floor_reason = _participation_floor(record)

    participation_step = next(
        (step for step in audit if step.get("category") == "Participation"), None
    )
    if participation_step is not None:
        participation_step["passed"] = bool(
            participation_step.get("passed") and floor_passed
        )
        evidence = list(participation_step.get("evidence") or [])
        evidence.append(floor_reason)
        participation_step["evidence"] = evidence
        if not floor_passed:
            participation_step["result"] = floor_reason

    # Participation is fuel for the low-float squeeze thesis, not an optional
    # confluence category. Three technical categories cannot promote a dead tape.
    if advanced and not floor_passed:
        advanced = False
        confluence = min(int(confluence or 0), 45)
        confluence_step = next(
            (step for step in audit if step.get("category") == "Confluence"), None
        )
        if confluence_step is not None:
            confluence_step["passed"] = False
            confluence_step["result"] = "Participation floor not met"
            evidence = list(confluence_step.get("evidence") or [])
            evidence.append("Low-RVOL promotion blocked unless multi-window ignition is confirmed")
            confluence_step["evidence"] = evidence

    return advanced, audit, confluence


YahooFinanceFloatProvider.parse = staticmethod(_conservative_yahoo_share_structure)
decision_engine.behavioral_decision = _behavioral_decision_with_participation_floor
