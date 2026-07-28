"""Independent early momentum discovery; never an execution predicate."""

from __future__ import annotations

MIN_DOLLAR_VOLUME = 250_000.0


def _num(record: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if record.get(key) is not None:
            try:
                return float(record[key])
            except (TypeError, ValueError):
                pass
    return default


def early_setup_evaluation(record: dict) -> dict:
    acceleration = max(
        _num(record, "volume_acceleration"),
        _num(record, "five_minute_acceleration", "acceleration_ratio"),
        _num(record, "vpi", "volume_pace_ratio"),
    )
    rvol = _num(record, "rvol", "rvol_proxy")
    pace = bool(record.get("volume_above_preceding_15m_pace"))
    participation = acceleration >= 1.5 or rvol >= 2 or pace
    relation = str(record.get("vwap_relation") or "").lower()
    above_vwap = relation == "above" or bool(record.get("price_above_vwap"))
    reclaimed = bool(record.get("vwap_reclaimed_last_10m"))
    bullish = bool(record.get("supertrend_bullish"))
    flipped = bool(record.get("supertrend_flipped_last_10m")) or (
        bool(record.get("supertrend_flip"))
        and _num(record, "supertrend_flip_age_seconds", default=601) <= 600
    )
    structures = {
        "above VWAP": above_vwap,
        "VWAP reclaimed": reclaimed,
        "SuperTrend bullish": bullish,
        "SuperTrend flipped": flipped,
        "crossed VWAP and SuperTrend": bool(record.get("crossed_vwap_and_supertrend")),
        "above 5 EMA and 60/65 EMA": bool(record.get("above_ema5_and_ema60_65"))
        or (
            str(record.get("ema5_relation") or "").lower() == "above"
            and str(record.get("ema65_relation") or "").lower() == "above"
        ),
        "higher lows": bool(record.get("higher_lows")),
    }
    structure_count = sum(structures.values())
    change, recent_gain = _num(record, "pct_change"), _num(
        record, "price_change_10m_pct", "ten_minute_gain_pct"
    )
    breakout = bool(record.get("broke_previous_15m_high_with_volume"))
    momentum = change >= 8 or recent_gain >= 4 or breakout
    fresh_news = (
        bool(record.get("headline"))
        and _num(record, "news_age_hours", default=999) <= 24
    )
    minimum_dollars = _num(record, "minimum_dollar_volume", default=MIN_DOLLAR_VOLUME)
    liquid = _num(record, "dollar_volume") >= minimum_dollars

    participation_points = min(30.0, max(acceleration / 3, rvol / 4) * 30)
    if pace:
        participation_points = max(participation_points, 18.0)
    structure_points = min(30.0, structure_count * 7.5)
    momentum_points = min(
        20.0, max(change / 16, recent_gain / 8, 1.0 if breakout else 0.0) * 20
    )
    score = round(
        participation_points
        + structure_points
        + momentum_points
        + (10 if fresh_news else 0)
        + min(10, _num(record, "dollar_volume") / max(minimum_dollars, 1) * 10),
        1,
    )
    override = acceleration >= 3 and above_vwap and (bullish or flipped) and score >= 55
    qualified = (
        liquid
        and participation
        and structure_count >= 2
        and momentum
        and (score >= 60 or override)
    )
    next_condition = (
        "hold above VWAP"
        if above_vwap
        else (
            "reclaim VWAP"
            if not reclaimed
            else "confirm SuperTrend" if not bullish else "maintain volume expansion"
        )
    )
    return {
        "qualified": qualified,
        "state": "EARLY SETUP" if qualified else "Discovered",
        "score": score,
        "override": override,
        "volume_acceleration": round(acceleration, 2),
        "structure_count": structure_count,
        "structure_conditions": [k for k, v in structures.items() if v],
        "next_condition": next_condition,
        "vwap_status": "reclaimed" if reclaimed else "above" if above_vwap else "below",
        "supertrend_status": (
            "just flipped" if flipped else "bullish" if bullish else "bearish"
        ),
    }


def enrich_early_setups(records: list[dict]) -> list[dict]:
    output = []
    for source in records:
        record, result = dict(source), early_setup_evaluation(source)
        record.update(
            early_setup=result,
            early_setup_qualified=result["qualified"],
            early_setup_score=result["score"],
            discovery_state=result["state"],
        )
        output.append(record)
    return output


def top_early_setups(records: list[dict], limit: int = 5) -> list[dict]:
    return sorted(
        (r for r in records if r.get("early_setup_qualified")),
        key=lambda r: (-_num(r, "early_setup_score"), str(r.get("symbol") or "")),
    )[:limit]


def newly_entered_symbols(
    records: list[dict], active_symbols: set[str]
) -> tuple[list[str], set[str]]:
    current = {
        str(r.get("symbol") or "").upper()
        for r in records
        if r.get("early_setup_qualified") and r.get("symbol")
    }
    return sorted(current - set(active_symbols)), current
