"""Independent early momentum discovery; never an execution predicate."""

from __future__ import annotations

from datetime import datetime, timezone

MIN_DOLLAR_VOLUME = 250_000.0


def _num(record: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if record.get(key) is not None:
            try:
                return float(record[key])
            except (TypeError, ValueError):
                pass
    return default


def _time(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _iso(value) -> str | None:
    parsed = _time(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def _event_time(
    record: dict, prior: dict, key: str, active: bool, now: datetime
) -> str | None:
    return _iso(record.get(key) or prior.get(key)) or (
        now.isoformat().replace("+00:00", "Z") if active else None
    )


def early_setup_evaluation(record: dict, prior: dict | None = None) -> dict:
    prior = prior or {}
    now = _time(record.get("scan_time") or record.get("timestamp")) or datetime.now(
        timezone.utc
    )
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

    abnormal = participation and liquid
    first_detection_time = _event_time(
        record, prior, "first_abnormal_volume_time", abnormal, now
    )
    first_detection_price = _num(
        record,
        "first_abnormal_volume_price",
        default=_num(
            prior, "first_abnormal_volume_price", default=_num(record, "price")
        ),
    )
    current_price = _num(record, "price")
    move_since_detection = (
        ((current_price / first_detection_price) - 1) * 100
        if current_price and first_detection_price
        else 0.0
    )
    first_vwap_reclaim_time = _event_time(
        record, prior, "first_vwap_reclaim_time", reclaimed, now
    )
    first_supertrend_flip_time = _event_time(
        record, prior, "first_supertrend_flip_time", flipped, now
    )
    breakout_time = _event_time(record, prior, "breakout_time", breakout, now)
    first_halt_time = _event_time(
        record,
        prior,
        "first_halt_time",
        bool(record.get("halted") or record.get("halt_detected")),
        now,
    )
    reclaim_price = _num(
        record,
        "most_recent_vwap_reclaim_price",
        "vwap_reclaim_price",
        default=_num(prior, "most_recent_vwap_reclaim_price", "vwap_reclaim_price"),
    )
    breakout_age_bars = _num(
        record, "breakout_age_completed_bars", "bars_since_breakout", default=999
    )
    flip_age_bars = _num(
        record,
        "supertrend_flip_age_completed_bars",
        "bars_since_supertrend_flip",
        default=999,
    )
    timing_conditions = {
        "within 8% of abnormal-volume detection": move_since_detection <= 8,
        "within 5% of VWAP reclaim": bool(reclaim_price)
        and current_price <= reclaim_price * 1.05,
        "breakout within 3 completed bars": breakout and breakout_age_bars <= 3,
        "SuperTrend flip within 5 completed bars": flipped and flip_age_bars <= 5,
        "no halt since first detection": not bool(first_halt_time),
    }

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
    previously_late = str(
        prior.get("timing_state")
        or (prior.get("early_setup") or {}).get("timing_state")
        or ""
    ).upper() in {"LATE MOMENTUM", "WAIT FOR RESET"}
    timing_qualified = any(timing_conditions.values()) and not previously_late
    early_qualified = qualified and timing_qualified
    late_state = (
        "WAIT FOR RESET"
        if bool(record.get("pullback") or record.get("reset_in_progress"))
        else "LATE MOMENTUM"
    )
    state = (
        "EARLY SETUP" if early_qualified else late_state if qualified else "Discovered"
    )
    detection_time = _time(first_detection_time)
    detection_delay = (
        max(0, int((now - detection_time).total_seconds())) if detection_time else 0
    )
    return {
        "qualified": early_qualified,
        "base_qualified": qualified,
        "timing_qualified": timing_qualified,
        "timing_state": state,
        "state": state,
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
        "timing_conditions": [key for key, value in timing_conditions.items() if value],
        "first_abnormal_volume_time": first_detection_time,
        "first_abnormal_volume_price": first_detection_price,
        "first_vwap_reclaim_time": first_vwap_reclaim_time,
        "first_supertrend_flip_time": first_supertrend_flip_time,
        "breakout_time": breakout_time,
        "first_halt_time": first_halt_time,
        "percent_move_since_first_detection": round(move_since_detection, 1),
        "detection_delay_seconds": detection_delay,
        "alert_eligible": early_qualified and move_since_detection <= 12,
    }


def enrich_early_setups(
    records: list[dict], previous_by_symbol: dict[str, dict] | None = None
) -> list[dict]:
    previous_by_symbol = previous_by_symbol or {}
    output = []
    for source in records:
        record = dict(source)
        prior = previous_by_symbol.get(str(source.get("symbol") or ""), {})
        result = early_setup_evaluation(source, prior)
        record.update(
            early_setup=result,
            early_setup_qualified=result["qualified"],
            early_setup_score=result["score"],
            discovery_state=result["state"],
            timing_state=result["timing_state"],
            early_setup_alert_eligible=result["alert_eligible"],
        )
        for key in (
            "first_abnormal_volume_time",
            "first_abnormal_volume_price",
            "first_vwap_reclaim_time",
            "first_supertrend_flip_time",
            "breakout_time",
            "first_halt_time",
            "percent_move_since_first_detection",
            "detection_delay_seconds",
        ):
            record[key] = result[key]
        output.append(record)
    return output


def top_early_setups(records: list[dict], limit: int = 5) -> list[dict]:
    return sorted(
        (r for r in records if r.get("early_setup_qualified")),
        key=lambda r: (-_num(r, "early_setup_score"), str(r.get("symbol") or "")),
    )[:limit]


def top_timing_setups(records: list[dict], limit: int = 5) -> list[dict]:
    """Return qualified ignition candidates, including honest late classifications."""
    return sorted(
        (r for r in records if (r.get("early_setup") or {}).get("base_qualified")),
        key=lambda r: (-_num(r, "early_setup_score"), str(r.get("symbol") or "")),
    )[:limit]


def newly_entered_symbols(
    records: list[dict], active_symbols: set[str]
) -> tuple[list[str], set[str]]:
    current = {
        str(r.get("symbol") or "").upper()
        for r in records
        if r.get("early_setup_alert_eligible") and r.get("symbol")
    }
    return sorted(current - set(active_symbols)), current
