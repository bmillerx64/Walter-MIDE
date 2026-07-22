from __future__ import annotations

STATE_RANK = {
    "Removed": 0,
    "Weakening": 1,
    "New": 2,
    "Watching": 3,
    "Emerging": 4,
    "Strengthening": 5,
    "Entry Ready": 6,
}

WATCH_STATES = {"Watching", "Emerging", "Strengthening", "Entry Ready"}


def _num(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _tf_bull(record: dict, label: str) -> bool:
    tf = record.get("timeframes") or {}
    item = tf.get(label) or {}
    return bool(item.get("above_vwap") and item.get("supertrend"))


def _tf_detail(record: dict, label: str) -> dict:
    return (record.get("timeframes") or {}).get(label) or {}


def _tf_supportive(record: dict, label: str) -> bool:
    item = _tf_detail(record, label)
    return bool(
        item.get("supertrend")
        or item.get("near_supertrend_flip")
        or item.get("very_close_to_flipping")
    )


def _entry_ready_requirements(record: dict, prior: dict | None = None) -> bool:
    price_at_or_above_vwap = record.get("vwap_relation") == "above" or _num(record, "vwap_distance_pct") >= 0
    catalyst_30s = bool(record.get("supertrend_30s_flip", record.get("supertrend_flip")))
    one_min_support = _tf_supportive(record, "1m") or bool(record.get("supertrend_bullish"))
    three_min_support = _tf_supportive(record, "3m")

    return all([
        catalyst_30s,
        price_at_or_above_vwap,
        one_min_support,
        three_min_support,
    ])

def momentum_evidence(record: dict, prior: dict | None = None) -> tuple[float, list[str], list[str]]:
    """Score developing momentum without requiring a completed setup."""
    prior = prior or {}
    reasons: list[str] = []
    cautions: list[str] = []
    points = 0.0

    discovery = set(record.get("discovery_reasons") or [])
    if record.get("headline"):
        points += 16
        reasons.append("recent news catalyst")
    elif "recent news" in discovery:
        points += 10
        reasons.append("news-driven discovery")

    vol = _num(record, "volume")
    dollar = _num(record, "dollar_volume")
    rvol = _num(record, "rvol_proxy", 1)
    accel = _num(record, "volume_acceleration", 1)
    turnover = _num(record, "float_turnover_pct")

    if vol >= 500_000:
        points += min(14, 5 + vol / 2_000_000)
        reasons.append("increasing feed volume")
    if dollar >= 250_000:
        points += min(12, 4 + dollar / 1_500_000)
        reasons.append("increasing dollar volume")
    if rvol >= 1.5:
        points += min(14, 5 + (rvol - 1.5) * 2.5)
        reasons.append(f"rising RVOL {rvol:.1f}×")
    if accel >= 1.2:
        points += min(14, 4 + (accel - 1.0) * 8)
        reasons.append(f"accelerating volume {accel:.1f}×")
    if turnover >= 3:
        points += min(10, turnover)
        reasons.append(f"float turnover {turnover:.1f}%")

    if abs(_num(record, "pct_change")) <= 4 and accel >= 1.2:
        points += 8
        reasons.append("flat base with activity expanding")

    was_below = prior.get("vwap_relation") == "below"
    if record.get("vwap_relation") in {"testing", "above"}:
        points += 8
        reasons.append("VWAP improving" if was_below else "near/above VWAP")
    if was_below and record.get("vwap_relation") == "above":
        points += 12
        reasons.append("VWAP reclaim")

    if record.get("supertrend_flip"):
        points += 10
        reasons.append("30-second SuperTrend flip")
    elif record.get("supertrend_bullish"):
        points += 5
        reasons.append("SuperTrend supportive")

    for label, text, pts in [("1m", "1-minute confirmation", 7), ("3m", "3-minute confirmation", 6), ("5m", "5-minute confirmation", 5)]:
        if _tf_bull(record, label):
            points += pts
            reasons.append(text)

    if record.get("higher_lows"):
        points += 8
        reasons.append("higher lows")
    if record.get("ema65_relation") == "above":
        points += 5
        reasons.append("above EMA65")

    if prior:
        if vol > _num(prior, "volume") * 1.05:
            points += 7
            reasons.append("feed volume increased since prior scan")
        if dollar > _num(prior, "dollar_volume") * 1.05:
            points += 7
            reasons.append("dollar flow increased since prior scan")
        if rvol > _num(prior, "rvol_proxy", 1) + 0.25:
            points += 6
            reasons.append("RVOL improved since prior scan")
        if _num(record, "opportunity_score") > _num(prior, "opportunity_score") + 3:
            points += 5
            reasons.append("momentum score improving")

    if _num(record, "spread_pct") > 6:
        points -= 20
        cautions.append("wide spread")
    if record.get("risk_flags"):
        points -= min(25, len(record.get("risk_flags") or []) * 8)
        cautions.append("headline risk flags present")

    return max(0.0, min(100.0, points)), reasons[:12], cautions[:6]


def classify_state(record: dict, prior: dict | None = None) -> str:
    score, reasons, cautions = momentum_evidence(record, prior)
    prior_state = (prior or {}).get("candidate_status") or (prior or {}).get("status")
    if _num(record, "dollar_volume") < 50_000 or _num(record, "spread_pct") > 10:
        return "Removed"
    if _entry_ready_requirements(record, prior):
        return "Entry Ready"
    if prior and score < _num(prior, "scanner_v2_score", _num(prior, "opportunity_score")) - 12:
        return "Weakening"
    if score >= 66:
        return "Strengthening"
    if score >= 52:
        return "Emerging"
    if score >= 34 or record.get("headline") or _num(record, "rvol_proxy", 1) >= 1.5:
        return "Watching"
    return "New" if not prior_state else "Removed"


def apply_scanner_v2(records: list[dict], previous_by_symbol: dict[str, dict]) -> list[dict]:
    output = []
    for source in records:
        record = dict(source)
        prior = previous_by_symbol.get(record.get("symbol"), {})
        score, reasons, cautions = momentum_evidence(record, prior)
        state = classify_state(record, prior)
        previous_state = prior.get("candidate_status") or prior.get("status")
        advanced = STATE_RANK.get(state, 0) > STATE_RANK.get(previous_state, 0)
        entered_watch = state in WATCH_STATES and previous_state not in WATCH_STATES
        record.update({
            "scanner_version": "V2",
            "scanner_v2_score": round(score, 1),
            "candidate_status": state,
            "previous_candidate_status": previous_state or "None",
            "advanced_state": advanced,
            "entered_watchlist": entered_watch,
            "alert_event": bool(entered_watch or advanced),
            "status": state,
            "reasons": reasons or record.get("reasons", []),
            "cautions": list(dict.fromkeys((record.get("cautions") or []) + cautions)),
        })
        output.append(record)
    return sorted(output, key=lambda r: (STATE_RANK.get(r.get("candidate_status"), 0), r.get("scanner_v2_score", 0)), reverse=True)
