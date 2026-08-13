"""Post-decision outcome measurement for immutable Walter evidence.

Outcome labels are deliberately downstream. They may evaluate a historical decision,
but they must never feed future information back into live discovery, scoring,
qualification, ranking, alerts, or entry state.
"""

from __future__ import annotations

from datetime import datetime, timezone

from mide.decision_time_evidence import verify_decision_time_evidence


class InvalidOutcomeWindow(ValueError):
    """Raised when forward bars cannot safely label a decision-time observation."""


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def measure_forward_outcome(evidence: dict, bars: list[dict], *, horizon_minutes: int) -> dict:
    """Measure MFE/MAE using only bars strictly after the recorded decision timestamp."""
    if not verify_decision_time_evidence(evidence):
        raise InvalidOutcomeWindow("decision-time evidence failed integrity verification")
    if horizon_minutes <= 0:
        raise InvalidOutcomeWindow("horizon_minutes must be positive")

    entry = float(evidence.get("price") or 0)
    if entry <= 0:
        raise InvalidOutcomeWindow("decision-time price must be positive")

    decision_at = _dt(evidence.get("scan_timestamp"))
    horizon_seconds = horizon_minutes * 60
    eligible = []
    for bar in bars or []:
        stamp = _dt(bar.get("timestamp") or bar.get("t"))
        age = (stamp - decision_at).total_seconds()
        if 0 < age <= horizon_seconds:
            eligible.append((stamp, bar))

    if not eligible:
        raise InvalidOutcomeWindow("no strictly forward bars exist inside the requested horizon")

    eligible.sort(key=lambda item: item[0])
    highs = [float(bar.get("high", bar.get("h"))) for _, bar in eligible]
    lows = [float(bar.get("low", bar.get("l"))) for _, bar in eligible]
    closes = [float(bar.get("close", bar.get("c"))) for _, bar in eligible]
    max_high = max(highs)
    min_low = min(lows)
    mfe_pct = ((max_high / entry) - 1.0) * 100.0
    mae_pct = ((min_low / entry) - 1.0) * 100.0
    end_pct = ((closes[-1] / entry) - 1.0) * 100.0
    peak_index = highs.index(max_high)

    return {
        "scan_id": evidence.get("scan_id"),
        "symbol": evidence.get("symbol"),
        "decision_timestamp": evidence.get("scan_timestamp"),
        "evidence_sha256": evidence.get("evidence_sha256"),
        "entry_price": entry,
        "horizon_minutes": int(horizon_minutes),
        "bars_observed": len(eligible),
        "mfe_pct": mfe_pct,
        "mae_pct": mae_pct,
        "end_return_pct": end_pct,
        "time_to_mfe_seconds": (eligible[peak_index][0] - decision_at).total_seconds(),
        "max_forward_high": max_high,
        "min_forward_low": min_low,
        "outcome_source": "strictly post-decision bars",
    }
