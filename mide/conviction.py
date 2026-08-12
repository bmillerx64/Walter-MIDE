"""Walter 2.2 dynamic conviction explanations.

Conviction is presentation-only.  It consumes completed scanner decisions and
never qualifies, promotes, triggers, or ranks a candidate.
"""

from __future__ import annotations


CONVICTION_WEIGHTS = {
    "participation": 30.0,
    "dollar_flow": 20.0,
    "trend": 20.0,
    "structure": 15.0,
    "catalyst": 10.0,
    "opportunity": 5.0,
}
MAX_CONVICTION_HISTORY = 5
MATERIAL_CHANGE = 5.0


def _number(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _change(current: float, previous: float) -> float:
    """Return a bounded percent change without exploding from a zero base."""
    if previous <= 0:
        return 0.0
    return _clamp((current / previous - 1.0) * 100.0, -100.0, 100.0)


def _points(quality: float, maximum: float) -> float:
    return round(_clamp(quality) * maximum / 100.0, 1)


def calculate_conviction(record: dict, prior: dict | None = None) -> dict:
    """Build deterministic scan-to-scan conviction and trader-facing copy."""
    prior = prior or {}
    participation = max(
        _number(record, "participation_score"),
        _number(record, "participation_surge_score"),
    )
    prior_participation = max(
        _number(prior, "participation_score", participation),
        _number(prior, "participation_surge_score", participation),
    )
    volume_acceleration = _number(record, "volume_acceleration", 1.0)
    prior_acceleration = _number(prior, "volume_acceleration", volume_acceleration)
    volume_change = _change(_number(record, "volume"), _number(prior, "volume"))
    participation_change = participation - prior_participation
    acceleration_change = (volume_acceleration - prior_acceleration) * 30.0
    participation_quality = _clamp(
        45.0 + participation_change * 1.5 + acceleration_change + volume_change * 0.35
    )

    dollar_change = _change(
        _number(record, "dollar_volume"), _number(prior, "dollar_volume")
    )
    dollar_quality = _clamp(50.0 + dollar_change * 1.25)

    confirmations = min(4.0, _number(record, "timeframe_confirmations"))
    prior_confirmations = min(4.0, _number(prior, "timeframe_confirmations", confirmations))
    trend_quality = _clamp(
        35.0
        + (25.0 if record.get("supertrend_bullish") else -20.0)
        + (15.0 if record.get("ema65_relation") == "above" else -10.0)
        + (confirmations - prior_confirmations) * 12.0
        + (15.0 if record.get("supertrend_bullish") and not prior.get("supertrend_bullish") and prior else 0.0)
    )

    relation = record.get("vwap_relation")
    structure_quality = 45.0
    structure_quality += 25.0 if relation == "above" else 5.0 if relation == "testing" else -25.0
    structure_quality += 20.0 if record.get("higher_lows") else 0.0
    extension = max(0.0, _number(record, "vwap_distance_pct"))
    if relation == "above" and extension > 2.0:
        structure_quality -= min(45.0, (extension - 2.0) * 12.0)
    structure_quality = _clamp(structure_quality)

    catalyst_quality = 20.0
    if record.get("headline"):
        catalyst_quality = _clamp(65.0 + _number(record, "catalyst_score") * 3.0)
    opportunity_quality = _clamp(_number(record, "opportunity_score_v2"))
    qualities = {
        "participation": participation_quality,
        "dollar_flow": dollar_quality,
        "trend": trend_quality,
        "structure": structure_quality,
        "catalyst": catalyst_quality,
        "opportunity": opportunity_quality,
    }
    components = {
        name: _points(quality, CONVICTION_WEIGHTS[name])
        for name, quality in qualities.items()
    }
    score = round(_clamp(sum(components.values())), 1)
    # Seed a legacy candidate's first comparison from the same deterministic
    # formula rather than showing a false zero/steady transition.
    old_score = (
        _number(prior, "conviction_v2_score")
        if "conviction_v2_score" in prior
        else calculate_conviction(prior)["conviction_v2_score"]
        if prior
        else score
    )
    delta = round(score - old_score, 1)
    trend = "Rising" if delta > 1 else "Falling" if delta < -1 else "Steady"
    history = list(prior.get("conviction_history") or [])
    if prior and not history:
        history = [round(old_score, 1)]
    history = (history + [score])[-MAX_CONVICTION_HISTORY:]

    contributors: list[tuple[float, str]] = [
        (participation_change + acceleration_change, "Participation accelerated" if participation_change + acceleration_change >= 0 else "Participation faded"),
        (dollar_change, "Dollar flow increased" if dollar_change >= 0 else "Dollar flow decreased"),
        ((1 if record.get("supertrend_bullish") else -1) * 12, "SuperTrend confirmed" if record.get("supertrend_bullish") else "Trend confirmation weakened"),
        (-extension * 3 if extension > 2 else 4, "Price structure is supported" if extension <= 2 else "Price is extending without added support"),
    ]
    contributors.sort(key=lambda item: abs(item[0]), reverse=True)
    change_reasons = [text for _, text in contributors[:3]] if abs(delta) >= MATERIAL_CHANGE else []

    watching = [
        {"label": "Volume accelerating", "complete": volume_acceleration > 1.0},
        {"label": "Dollar flow increasing", "complete": dollar_change > 0},
        {"label": "VWAP reclaimed", "complete": relation == "above"},
        {"label": "Pullback defended", "complete": bool(record.get("higher_lows"))},
        {"label": "Fresh trigger", "complete": record.get("trigger") == "YES"},
    ]

    positive = (
        "Buyers are getting more aggressive."
        if participation_change > 3 or acceleration_change > 5
        else "Participation is supporting the setup."
        if participation_quality >= 50
        else "Price structure still offers something constructive to watch."
    )
    middle = (
        "Volume and dollar flow are expanding together."
        if volume_change > 0 and dollar_change > 0
        else "Participation is improving, but confirmation is incomplete."
        if delta >= 0
        else "Participation has eased since the previous scan."
    )
    guidance = (
        "Wait for a controlled pullback rather than chasing price."
        if extension > 2 and relation == "above"
        else "Momentum remains constructive while buyers hold VWAP."
        if relation == "above"
        else "Walter is waiting for buyers to reclaim VWAP."
    )
    return {
        "conviction_v2_score": score,
        "conviction_trend": trend,
        "conviction_delta": delta,
        "conviction_history": history,
        "conviction_components": components,
        "conviction_component_maximums": dict(CONVICTION_WEIGHTS),
        "conviction_change_reasons": change_reasons,
        "walter_watching": watching,
        "walter_take": " ".join([positive, middle, guidance]),
    }


def enrich_conviction(record: dict, prior: dict | None = None) -> dict:
    record.update(calculate_conviction(record, prior))
    return record
