from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass
class Evidence:
    symbol: str
    price: float
    pct_change: float
    volume: float
    dollar_volume: float
    spread_pct: float
    vwap_relation: str
    vwap_distance_pct: float
    supertrend_bullish: bool
    supertrend_flip: bool
    ema65_relation: str
    ema65_distance_pct: float
    volume_acceleration: float
    green_volume_ratio: float
    rvol_proxy: float
    higher_lows: bool
    near_hod: bool
    catalyst_score: float
    headline: str
    news_age_hours: float | None
    risk_flags: list[str]
    timeframe_confirmations: int
    discovery_reasons: list[str]


@dataclass
class Decision:
    opportunity_score: float
    conviction_score: float
    status: str
    participation_score: float
    participation_tier: str
    attention_score: float
    reasons: list[str]
    cautions: list[str]


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _scaled_log_points(value: float, floor: float, ceiling: float, points: float) -> float:
    """Graduated score that does not saturate at modest volume levels."""
    if value <= floor:
        return 0.0
    if ceiling <= floor:
        return points
    ratio = math.log10(value / floor) / math.log10(ceiling / floor)
    return _clamp(ratio * points, 0.0, points)


def _participation_tier(score_value: float) -> str:
    if score_value >= 82:
        return "DOMINANT"
    if score_value >= 68:
        return "EXCEPTIONAL"
    if score_value >= 52:
        return "STRONG"
    if score_value >= 35:
        return "ACTIVE"
    return "ORDINARY"


def score(e: Evidence) -> Decision:
    reasons: list[str] = []
    cautions: list[str] = []

    # Participation v0.7: reward scale, not merely threshold crossing.
    # Share volume remains distinct from dollar flow so penny-stock leaders can stand out.
    share_points = _scaled_log_points(e.volume, 100_000, 100_000_000, 22)
    dollar_points = _scaled_log_points(e.dollar_volume, 100_000, 250_000_000, 16)
    rvol_points = min(24, max(0, math.log2(max(e.rvol_proxy, 1.0)) * 6))
    acceleration_points = min(20, max(0, (e.volume_acceleration - 1) * 13))
    green_points = min(10, max(0, (e.green_volume_ratio - 1) * 5))
    mover_points = min(8, max(0, e.pct_change / 5))

    participation = _clamp(
        share_points + dollar_points + rvol_points + acceleration_points + green_points + mover_points
    )
    tier = _participation_tier(participation)

    if e.volume >= 20_000_000:
        reasons.append(f"Major share participation: {e.volume / 1_000_000:.1f}M")
    elif e.volume >= 5_000_000:
        reasons.append(f"Strong share participation: {e.volume / 1_000_000:.1f}M")
    if e.dollar_volume >= 25_000_000:
        reasons.append(f"Heavy dollar flow: ${e.dollar_volume / 1_000_000:.1f}M")
    if e.pct_change >= 5:
        reasons.append(f"Top-mover behavior: {e.pct_change:.1f}%")

    technical = 0.0
    if e.vwap_relation == "above":
        technical += 22
        reasons.append("Above VWAP")
    elif e.vwap_relation == "testing":
        technical += 14
        reasons.append("Testing VWAP")
    else:
        cautions.append(f"Below VWAP by {e.vwap_distance_pct:.1f}%")

    if e.supertrend_bullish:
        technical += 18
        reasons.append("SuperTrend bullish")
    if e.supertrend_flip:
        technical += 10
        reasons.append("Fresh SuperTrend flip")
    if e.ema65_relation == "above":
        technical += 14
        reasons.append("Above 65 EMA")
    elif e.ema65_distance_pct <= 1.5:
        technical += 8
        reasons.append("Testing 65 EMA")
    if e.higher_lows:
        technical += 10
        reasons.append("Higher lows")
    if e.near_hod:
        technical += 8
        reasons.append("Near high of day")
    technical += min(18, e.timeframe_confirmations * 4.5)
    technical = _clamp(technical)

    context = 38.0
    if e.headline:
        context += e.catalyst_score
        age = e.news_age_hours
        if age is not None:
            if age <= 3:
                context += 12
                reasons.append("Fresh corporate news")
            elif age <= 30:
                context += 7
                reasons.append("Prior-day news remains relevant")
            elif age <= 72:
                context += 2
        if e.catalyst_score > 0:
            reasons.append("Positive catalyst language")
        elif e.catalyst_score < 0:
            cautions.append("Negative or dilution-related headline")
    else:
        cautions.append("No confirmed news catalyst")
    context = _clamp(context)

    risk = 78.0
    if e.spread_pct > 6:
        risk -= 35
        cautions.append(f"Wide spread: {e.spread_pct:.1f}%")
    elif e.spread_pct > 3:
        risk -= 15
        cautions.append(f"Elevated spread: {e.spread_pct:.1f}%")
    if e.dollar_volume < 100_000:
        risk -= 30
        cautions.append("Thin dollar volume")
    elif e.dollar_volume < 500_000:
        risk -= 12
    severe = {"offering", "registered direct", "public offering", "bankruptcy", "delisting"}
    if any(flag in severe for flag in e.risk_flags):
        risk -= 45
    risk = _clamp(risk)

    opportunity = (
        technical * 0.34
        + participation * 0.37
        + context * 0.16
        + risk * 0.13
    )
    evidence_count = sum([
        e.vwap_relation in {"above", "testing"},
        e.supertrend_bullish,
        e.ema65_relation == "above" or e.ema65_distance_pct <= 1.5,
        e.volume_acceleration >= 1.4,
        e.rvol_proxy >= 2,
        e.higher_lows,
        e.near_hod,
        bool(e.headline),
        e.timeframe_confirmations >= 3,
        participation >= 68,
    ])
    conviction = _clamp(30 + evidence_count * 6.5 + min(14, dollar_points * 0.8))
    if e.risk_flags:
        conviction -= min(25, len(e.risk_flags) * 8)
    conviction = _clamp(conviction)

    # Base attention score is augmented later with cohort dominance percentiles.
    attention = _clamp(opportunity * 0.52 + participation * 0.48)

    hard_pass = (
        e.price < 0.02
        or e.price > 5.0
        or e.dollar_volume < 50_000
        or e.spread_pct > 10
        or any(flag in severe for flag in e.risk_flags)
    )
    if hard_pass:
        status = "PASS"
    elif attention >= 86 and participation >= 68:
        status = "EXCEPTIONAL"
    elif opportunity >= 82 and conviction >= 68:
        status = "ALERT"
    elif opportunity >= 70 and conviction >= 56:
        status = "WATCH NOW"
    elif opportunity >= 54:
        status = "MONITOR"
    else:
        status = "PASS"

    if e.volume_acceleration >= 1.5:
        reasons.append(f"Volume accelerating {e.volume_acceleration:.1f}×")
    if e.rvol_proxy >= 2:
        reasons.append(f"RVOL proxy {e.rvol_proxy:.1f}×")

    return Decision(
        round(opportunity, 1),
        round(conviction, 1),
        status,
        round(participation, 1),
        tier,
        round(attention, 1),
        reasons[:10],
        cautions[:6],
    )
