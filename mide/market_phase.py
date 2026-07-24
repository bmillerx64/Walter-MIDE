from __future__ import annotations

from datetime import datetime, timezone

PHASE_EMERGING = "Emerging"
PHASE_MOMENTUM = "Momentum"
PHASE_DISTRIBUTION = "Distribution"
PHASE_BROKEN = "Broken"
MARKET_PHASES = (PHASE_EMERGING, PHASE_MOMENTUM, PHASE_DISTRIBUTION, PHASE_BROKEN)
PHASE_RANK = {phase: i for i, phase in enumerate(MARKET_PHASES)}
MAX_PHASE_TRANSITIONS = 50
BROKEN_REPROMOTION_SCANS = 3
CONFIRMATION_SCANS = 2


def _num(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _iso_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _tf_detail(record: dict, label: str) -> dict:
    return (record.get("timeframes") or {}).get(label) or {}


def _tf_supportive(record: dict, label: str) -> bool:
    item = _tf_detail(record, label)
    return bool(
        item.get("supertrend")
        or item.get("near_supertrend_flip")
        or item.get("very_close_to_flipping")
    )


def _tf_bull(record: dict, label: str) -> bool:
    item = _tf_detail(record, label)
    return bool(item.get("supertrend") or (item.get("above_vwap") and item.get("supertrend")))


def _vwap_supportive(record: dict) -> bool:
    return bool(record.get("vwap_relation") in {"above", "testing"} or _num(record, "vwap_distance_pct") >= -1.0)


def _above_vwap(record: dict) -> bool:
    return bool(record.get("vwap_relation") == "above" or _num(record, "vwap_distance_pct") >= 0)


def _participation_increasing(record: dict, prior: dict) -> bool:
    return bool(
        _num(record, "volume_acceleration", 1) >= 1.2
        or _num(record, "volume_pace_ratio", 1) >= 1.2
        or _num(record, "acceleration_ratio", 1) >= 1.2
        or _num(record, "rvol_proxy", 1) >= max(1.5, _num(prior, "rvol_proxy", 1) + 0.2)
        or (prior and _num(record, "volume") > _num(prior, "volume") * 1.05)
    )


def _early_momentum(record: dict, prior: dict) -> bool:
    return bool(
        record.get("supertrend_30s_flip", record.get("supertrend_flip"))
        or record.get("supertrend_bullish")
        or _num(record, "volume_acceleration", 1) >= 1.2
        or _num(record, "rvol_proxy", 1) >= 1.5
        or (prior and _num(record, "pct_change") > _num(prior, "pct_change") + 0.5)
    )


def _emerging_ready(record: dict, prior: dict) -> bool:
    return bool(
        _early_momentum(record, prior)
        and _vwap_supportive(record)
        and _participation_increasing(record, prior)
    )


def _momentum_ready(record: dict, prior: dict) -> bool:
    sequential_st = bool(
        (record.get("supertrend_30s_flip", record.get("supertrend_flip")) or record.get("supertrend_bullish"))
        and _tf_supportive(record, "1m")
        and _tf_supportive(record, "3m")
        and (_tf_supportive(record, "5m") or _tf_bull(record, "5m") or _num(record, "timeframe_confirmations") >= 3)
    )
    structure = bool(
        record.get("higher_lows")
        or record.get("near_hod")
        or (prior and _num(record, "price") >= _num(prior, "price") and _num(record, "pct_change") >= _num(prior, "pct_change") - 0.2)
    )
    return bool(sequential_st and _above_vwap(record) and structure and _participation_increasing(record, prior))


def _distribution_ready(record: dict, prior: dict) -> bool:
    st_losses = sum(
        [
            not bool(record.get("supertrend_bullish")),
            not _tf_supportive(record, "1m"),
            not _tf_supportive(record, "3m"),
            _tf_supportive(prior, "5m") and not _tf_supportive(record, "5m"),
        ]
    )
    fading = bool(
        _num(record, "volume_acceleration", 1) < 1.0
        or _num(record, "rvol_proxy", 1) < _num(prior, "rvol_proxy", 1) - 0.3
        or _num(record, "pct_change") < _num(prior, "pct_change") - 1.0
        or not record.get("higher_lows")
    )
    partially_intact = _vwap_supportive(record) or _tf_supportive(record, "3m") or _tf_supportive(record, "5m")
    return bool(st_losses >= 1 and fading and partially_intact)


def _broken_ready(record: dict, prior: dict) -> bool:
    st_failures = sum(
        [
            not bool(record.get("supertrend_bullish")),
            not _tf_supportive(record, "1m"),
            not _tf_supportive(record, "3m"),
            not _tf_supportive(record, "5m"),
        ]
    )
    exhausted = bool(
        not _vwap_supportive(record)
        or _num(record, "volume_acceleration", 1) < 0.8
        or _num(record, "rvol_proxy", 1) < 1.0
        or _num(record, "spread_pct") > 10
        or _num(record, "dollar_volume") < 50_000
    )
    return bool(st_failures >= 2 and exhausted)


def _candidate_phase(record: dict, prior: dict, current_phase: str) -> str:
    if _broken_ready(record, prior):
        return PHASE_BROKEN
    if current_phase == PHASE_BROKEN:
        return PHASE_EMERGING if _emerging_ready(record, prior) else PHASE_BROKEN
    if current_phase == PHASE_DISTRIBUTION:
        return PHASE_MOMENTUM if _momentum_ready(record, prior) else PHASE_DISTRIBUTION
    if _distribution_ready(record, prior):
        return PHASE_DISTRIBUTION
    if _momentum_ready(record, prior):
        return PHASE_MOMENTUM
    return PHASE_EMERGING


def apply_market_phase(record: dict, prior: dict | None = None, scan_time: datetime | None = None) -> dict:
    prior = prior or {}
    scan_time = scan_time or datetime.now(timezone.utc)
    stamp = _iso_timestamp(scan_time)
    previous_phase = prior.get("market_phase") if prior.get("market_phase") in MARKET_PHASES else PHASE_EMERGING
    candidate = _candidate_phase(record, prior, previous_phase)
    counters = dict(prior.get("market_phase_counters") or {})
    if candidate == previous_phase:
        counters = {candidate: int(counters.get(candidate, 0)) + 1}
        phase = previous_phase
    else:
        counters = {candidate: int(counters.get(candidate, 0)) + 1}
        needed = BROKEN_REPROMOTION_SCANS if previous_phase == PHASE_BROKEN and candidate != PHASE_BROKEN else CONFIRMATION_SCANS
        phase = candidate if counters[candidate] >= needed else previous_phase
    history = list(prior.get("market_phase_history") or [])
    if not history:
        history.append({"phase": previous_phase, "entered_at": prior.get("market_phase_entered_at") or stamp})
    transitioned = phase != previous_phase
    entered_at = prior.get("market_phase_entered_at") or stamp
    if transitioned:
        entered_at = stamp
        history.append({"phase": phase, "entered_at": stamp})
        counters = {phase: 1}
    return {
        "market_phase": phase,
        "previous_market_phase": previous_phase,
        "market_phase_transitioned": transitioned,
        "market_phase_entered_at": entered_at,
        "market_phase_history": history[-MAX_PHASE_TRANSITIONS:],
        "market_phase_counters": counters,
        "market_phase_candidate": candidate,
    }
