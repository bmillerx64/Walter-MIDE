"""GS455: admit early ignition and elevate ST/VWAP timeframe progression.

Live validation on 2026-09-15 exposed one coherent timing failure on RETO.

First, Webull surfaced RETO during the first minutes after the open while it was still
below Walter's ordinary 3% OR 100k-share prefilter. Second, the subsequent move showed
a clear SuperTrend/VWAP propagation ladder across 30s -> 1m -> 3m -> 5m -> 10m -> 15m.
Walter already had deterministic 1m/3m crossover truth, but later timeframe crosses were
not first-class operator evidence and the earliest 30s cross was not represented in the
same ladder.

GS455 sharpens that boundary without changing entry authority:

* 09:30-09:45 ET only: an already-discovered symbol may survive the cheap prefilter at
  >=2% AND >=15,000 shares. The ordinary prefilter resumes at 09:45.
* Reuse the already-fetched Stage-6 1m and 30s histories to reconstruct literal
  SuperTrend-line/VWAP-line crosses for 30s, 5m, 10m, and 15m while preserving GS378's
  canonical 1m/3m events.
* Build one ordered crossover progression. 30s/1m are ignition, 3m is confirmation,
  and 5m+ are persistence/maturation.
* A newly reached rung can create one tier-2 LOOK NOW operator pulse when structure and
  supporting flow remain constructive. Existing WATCH FOR ENTRY/entry authority wins,
  HALTED wins, and >5% VWAP extension remains CHASE / WAIT with an explicit DO NOT CHASE.

No additional provider request is made. No qualification, readiness, execution, order,
or entry threshold is widened.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time
from functools import wraps
from typing import Any

EARLY_OPEN_START = time(9, 30)
EARLY_OPEN_END = time(9, 45)
EARLY_OPEN_MIN_PCT_CHANGE = 2.0
EARLY_OPEN_MIN_VOLUME = 15_000.0

CROSSOVER_LADDER = ("30s", "1m", "3m", "5m", "10m", "15m")
_RESAMPLE_RULES = {
    "1m": None,
    "3m": "3min",
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
}
_NEW_WINDOWS_SECONDS = {
    "30s": 90.0,
    "1m": 120.0,
    "3m": 240.0,
    "5m": 360.0,
    "10m": 660.0,
    "15m": 960.0,
}
_RECENT_WINDOWS_SECONDS = {
    "30s": 10 * 60.0,
    "1m": 15 * 60.0,
    "3m": 20 * 60.0,
    "5m": 30 * 60.0,
    "10m": 50 * 60.0,
    "15m": 75 * 60.0,
}
LOOK_NOW_MAX_VWAP_DISTANCE_PCT = 5.0

_PREFILTER_FAILURE = "Percent change and average volume below thresholds"
_PROGRESSION_PROVENANCE = "ST_VWAP_CROSSOVER_PROGRESSION"


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _market_now():
    from .time_service import eastern_time

    return eastern_time()


def _inside_early_open_window() -> bool:
    now = _market_now()
    current = now.time().replace(tzinfo=None)
    return EARLY_OPEN_START <= current < EARLY_OPEN_END


def _early_open_prefilter_decision(original, symbol: str, snapshot: dict, settings) -> dict:
    """Apply one bounded early-open discovery exception to the existing decision."""
    base = original(symbol, snapshot, settings)
    if base.get("passed") or not _inside_early_open_window():
        return base
    if base.get("failed_rule") != _PREFILTER_FAILURE:
        return base

    measured = dict(base.get("measured_values") or {})
    pct_change = _number(measured, "pct_change", default=0.0) or 0.0
    volume = _number(measured, "volume", default=0.0) or 0.0
    if pct_change < EARLY_OPEN_MIN_PCT_CHANGE or volume < EARLY_OPEN_MIN_VOLUME:
        return base

    decision = deepcopy(base)
    decision["passed"] = True
    decision["failed_rule"] = None
    decision["failed_metrics"] = []
    decision["reason"] = (
        "passed prefilter via early-open ignition "
        f"(>={EARLY_OPEN_MIN_PCT_CHANGE:g}% and >={EARLY_OPEN_MIN_VOLUME:,.0f} shares)"
    )
    thresholds = dict(decision.get("thresholds") or {})
    thresholds["early_open_exception"] = {
        "window_et": "09:30-09:45",
        "min_pct_change": EARLY_OPEN_MIN_PCT_CHANGE,
        "min_volume": EARLY_OPEN_MIN_VOLUME,
    }
    decision["thresholds"] = thresholds
    return decision


def _halted(record: dict) -> bool:
    if any(
        record.get(key) is True
        for key in ("halted", "is_halted", "suspended", "is_suspended")
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).lower()
    return "halt" in text or "suspend" in text


def _current_attention(record: dict) -> bool:
    try:
        from .gs309_current_attention_mission import current_attention_provenance

        if current_attention_provenance(record):
            return True
    except Exception:
        pass
    return bool(
        str(record.get("headline") or "").strip()
        or record.get("fresh_news")
        or record.get("news_catalyst")
        or record.get("has_catalyst")
        or record.get("catalyst_confirmed")
    )


def _supporting_flow(record: dict) -> bool:
    volume = _number(record, "volume", default=0.0) or 0.0
    participation = _number(
        record, "participation_surge_score", "participation_score", default=0.0
    ) or 0.0
    expansion = _number(
        record, "expansion_quality", "expansion_score", default=0.0
    ) or 0.0
    volume_acceleration = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _number(
        record, "dollar_flow_acceleration_5m", "dollar_flow_acceleration", default=0.0
    ) or 0.0
    return bool(
        volume >= 100_000
        or participation >= 20.0
        or expansion >= 40.0
        or volume_acceleration >= 1.0
        or dollar_flow >= 1.25
        or _current_attention(record)
    )


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _resample_frame(day, label: str):
    from .indicators import resample_ohlcv

    rule = _RESAMPLE_RULES[label]
    return day if rule is None else resample_ohlcv(day, rule)


def _resample_vwap(primary_series, label: str):
    rule = _RESAMPLE_RULES[label]
    if rule is None:
        return primary_series
    return primary_series.resample(rule).last().dropna()


def _project_vwap_to_30s(primary_series, frame_30s):
    if primary_series is None or getattr(primary_series, "empty", True):
        return primary_series
    if frame_30s is None or getattr(frame_30s, "empty", True):
        return primary_series.iloc[0:0]
    combined = primary_series.index.union(frame_30s.index)
    expanded = primary_series.reindex(combined).sort_index().ffill()
    return expanded.reindex(frame_30s.index)


def _literal_cross_event(
    frame,
    vwap_series,
    label: str,
    *,
    latest_source_time=None,
) -> dict:
    """Reconstruct one literal ST-line/VWAP-line cross from local bars only."""
    from .indicators import supertrend

    if frame is None or getattr(frame, "empty", True) or len(frame) < 2:
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "age_bars": None,
            "current_confirmed": False,
        }

    vwap = vwap_series.reindex(frame.index)
    st_line, trend = supertrend(frame, 10, 3)
    valid = st_line.notna() & vwap.notna()
    close = frame["close"].astype(float)
    line_delta = st_line - vwap
    cross_mask = (
        valid
        & (line_delta.shift(1) < 0)
        & (line_delta >= 0)
        & trend.fillna(False).astype(bool)
        & (close >= vwap)
    )
    hits = list(cross_mask[cross_mask.fillna(False)].index)
    cross_time = hits[-1] if hits else None

    latest = latest_source_time if latest_source_time is not None else frame.index[-1]
    age_seconds = (
        max(0.0, (latest - cross_time).total_seconds())
        if cross_time is not None
        else None
    )
    age_bars = None
    if cross_time is not None:
        try:
            age_bars = max(0, len(frame) - 1 - int(frame.index.get_loc(cross_time)))
        except Exception:
            age_bars = None

    latest_vwap = vwap.iloc[-1] if len(vwap) else None
    latest_st = st_line.iloc[-1] if len(st_line) else None
    current_confirmed = bool(
        valid.iloc[-1]
        and bool(trend.iloc[-1])
        and float(close.iloc[-1]) >= float(latest_vwap)
    )
    event = {
        "timeframe": label,
        "crossed": cross_time is not None,
        "recent": bool(
            age_seconds is not None
            and age_seconds <= _RECENT_WINDOWS_SECONDS[label]
        ),
        "new": bool(
            age_seconds is not None and age_seconds <= _NEW_WINDOWS_SECONDS[label]
        ),
        "timestamp": cross_time.isoformat() if cross_time is not None else None,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "age_bars": age_bars,
        "current_confirmed": current_confirmed,
        "latest_supertrend_value": (
            round(float(latest_st), 6) if latest_st is not None else None
        ),
        "latest_vwap_value": (
            round(float(latest_vwap), 6) if latest_vwap is not None else None
        ),
    }
    if cross_time is not None:
        event.update(
            {
                "supertrend_value": round(float(st_line.loc[cross_time]), 6),
                "vwap_value": round(float(vwap.loc[cross_time]), 6),
                "price": round(float(close.loc[cross_time]), 6),
                "volume": round(float(frame.loc[cross_time, "volume"]), 2),
            }
        )
    return event


def extra_crossover_events(frame_1m, frame_30s=None) -> dict[str, dict]:
    """Compute 30s/5m/10m/15m events from histories Stage 6 already fetched."""
    from . import gs378_live_vwap_st_crossover as gs378

    day = gs378._eastern_day(frame_1m)
    if day.empty:
        return {}
    context = gs378.primary_vwap_context(day)
    primary = context.get("series")
    if primary is None or primary.empty:
        return {}

    latest_source_time = day.index[-1]
    events: dict[str, dict] = {}
    for label in ("5m", "10m", "15m"):
        tf = _resample_frame(day, label)
        vwap = _resample_vwap(primary, label)
        events[label] = _literal_cross_event(
            tf, vwap, label, latest_source_time=latest_source_time
        )

    thirty = gs378._eastern_day(frame_30s)
    if not thirty.empty:
        latest_source_time = max(latest_source_time, thirty.index[-1])
        projected = _project_vwap_to_30s(primary, thirty)
        events["30s"] = _literal_cross_event(
            thirty,
            projected,
            "30s",
            latest_source_time=latest_source_time,
        )
    else:
        events["30s"] = {
            "timeframe": "30s",
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "age_bars": None,
            "current_confirmed": False,
        }
    return events


def _current_confirmed(record: dict, label: str, event: dict) -> bool:
    if label in {"30s", "15m"}:
        return bool(event.get("current_confirmed"))
    frames = record.get("timeframes") or {}
    frame = frames.get(label) if isinstance(frames, dict) else None
    if isinstance(frame, dict):
        return bool(frame.get("above_vwap") and frame.get("supertrend"))
    return bool(event.get("current_confirmed"))


def crossover_progression(record: dict) -> dict:
    """Return the ordered current ST/VWAP propagation ladder for one symbol."""
    events = record.get("st_vwap_cross_events") or {}
    if not isinstance(events, dict):
        events = {}

    active_rungs: list[str] = []
    timestamps: list[datetime] = []
    fresh_rungs: list[str] = []
    for label in CROSSOVER_LADDER:
        event = dict(events.get(label) or {})
        if not event.get("crossed") or not _current_confirmed(record, label, event):
            continue
        active_rungs.append(label)
        stamp = _timestamp(event.get("timestamp"))
        if stamp is not None:
            timestamps.append(stamp)
        if event.get("new"):
            fresh_rungs.append(label)

    ordered = all(
        earlier <= later for earlier, later in zip(timestamps, timestamps[1:])
    )
    highest = active_rungs[-1] if active_rungs else None
    latest_new = fresh_rungs[-1] if fresh_rungs else None

    if any(label in active_rungs for label in ("5m", "10m", "15m")):
        stage = "PERSISTENCE"
    elif "3m" in active_rungs:
        stage = "CONFIRMATION"
    elif any(label in active_rungs for label in ("30s", "1m")):
        stage = "IGNITION"
    else:
        stage = "NONE"

    return {
        "ladder": list(CROSSOVER_LADDER),
        "active_rungs": active_rungs,
        "fresh_rungs": fresh_rungs,
        "depth": len(active_rungs),
        "ordered": ordered,
        "highest_rung": highest,
        "latest_new_rung": latest_new,
        "stage": stage,
        "sequence": " -> ".join(active_rungs),
    }


def _augment_progression_records(
    records: list[dict],
    current_session_raw: dict[str, list[dict]],
    current_session_30s_raw: dict[str, list[dict]] | None,
    client,
) -> list[dict]:
    """Attach detached progression evidence without changing score or qualification."""
    current_session_30s_raw = current_session_30s_raw or {}
    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        raw_1m = current_session_raw.get(symbol) or []
        if not raw_1m:
            continue
        try:
            frame_1m = client.bars_frame(raw_1m)
            frame_30s = client.bars_frame(current_session_30s_raw.get(symbol) or [])
            extras = extra_crossover_events(frame_1m, frame_30s)
        except Exception:
            continue

        events = dict(record.get("st_vwap_cross_events") or {})
        # Preserve GS378's canonical 1m/3m events exactly; add only missing rungs.
        for label in ("30s", "5m", "10m", "15m"):
            if label in extras:
                events[label] = extras[label]
        record["st_vwap_cross_events"] = events
        record["st_vwap_progression"] = crossover_progression(record)
    return records


def progression_signal(record: dict) -> dict:
    """Return a fresh operator signal from a newly reached ordered ladder rung."""
    progression = dict(record.get("st_vwap_progression") or crossover_progression(record))
    new_rung = progression.get("latest_new_rung")
    distance = _number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    above_vwap = relation == "above" or (distance is not None and distance >= 0.0)
    supported = _supporting_flow(record)
    depth = int(progression.get("depth") or 0)
    ordered = bool(progression.get("ordered"))
    active = bool(
        new_rung
        and not _halted(record)
        and above_vwap
        and supported
        and (ordered or depth <= 1)
    )
    event = dict((record.get("st_vwap_cross_events") or {}).get(new_rung) or {})
    return {
        "active": active,
        "new_rung": new_rung,
        "timestamp": event.get("timestamp"),
        "stage": progression.get("stage"),
        "sequence": progression.get("sequence") or "",
        "depth": depth,
        "ordered": ordered,
        "supporting_flow": supported,
        "vwap_distance_pct": distance,
    }


def _state_with_progression(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    signal = progression_signal(record)
    if not signal["active"]:
        return base
    if base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _PROGRESSION_PROVENANCE not in provenance:
        provenance.append(_PROGRESSION_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_vwap_progression"] = dict(
        record.get("st_vwap_progression") or crossover_progression(record)
    )

    rung = str(signal.get("new_rung") or "").upper()
    sequence = signal.get("sequence") or rung
    distance = signal.get("vwap_distance_pct")
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        view["state"] = unified.CHASE_WAIT
        view["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
        view["reason"] = (
            f"ST/VWAP progression reached {rung}; {sequence}. "
            f"Price is already {distance:.1f}% above VWAP."
        )
        view["next_step"] = (
            "LOOK NOW for continuation context, but DO NOT CHASE. The VWAP anti-chase "
            "guard remains authoritative; wait for a constructive reset."
        )
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = f"ST/VWAP progression reached {rung}; {sequence}."
    view["next_step"] = (
        "Open the chart now. The crossover ladder is operator-attention evidence, not "
        "entry authority; normal participation, expansion, readiness, and VWAP guards "
        "still decide the trade."
    )
    return view


def _progression_change(record: dict) -> dict | None:
    signal = progression_signal(record)
    if not signal.get("active"):
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    rung = str(signal.get("new_rung") or "").upper()
    stamp = str(signal.get("timestamp") or "unknown")
    return {
        "symbol": symbol,
        "from": f"{rung} CROSS@{stamp}",
        "to": f"ST/VWAP PROGRESSION {rung}",
    }


def _spoken_rung(label: str) -> str:
    return {
        "30s": "30 second",
        "1m": "1 minute",
        "3m": "3 minute",
        "5m": "5 minute",
        "10m": "10 minute",
        "15m": "15 minute",
    }.get(label, label)


def _progression_phrase(records: list[dict]) -> str:
    choices = []
    for record in records or []:
        signal = progression_signal(record)
        if signal.get("active"):
            rank = CROSSOVER_LADDER.index(signal["new_rung"])
            choices.append((rank, record, signal))
    if not choices:
        return ""

    _, record, signal = max(choices, key=lambda item: item[0])
    symbol = str(record.get("symbol") or "Symbol").strip().upper() or "SYMBOL"
    rung = _spoken_rung(str(signal.get("new_rung") or ""))
    stage = str(signal.get("stage") or "").lower()
    phrase = (
        f"{symbol}. LOOK NOW. SuperTrend VWAP progression reached {rung}. "
        f"{stage.capitalize()} advancing."
    )
    distance = signal.get("vwap_distance_pct")
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        phrase += " Extended. Do not chase."
    return phrase


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_prefilter() -> None:
    from . import discovery, flight_recorder

    current = flight_recorder.prefilter_decision
    if getattr(current, "_gs455_early_open_ignition", False):
        discovery.prefilter_decision = current
        return

    @wraps(current)
    def prefilter_decision(symbol: str, snapshot: dict, settings) -> dict:
        return _early_open_prefilter_decision(current, symbol, snapshot, settings)

    _inherit(prefilter_decision, current)
    prefilter_decision._gs455_early_open_ignition = True
    prefilter_decision._gs455_original = current
    flight_recorder.prefilter_decision = prefilter_decision
    discovery.prefilter_decision = prefilter_decision


def _install_progression_evidence() -> None:
    from . import gs378_live_vwap_st_crossover as gs378

    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs455_crossover_progression", False):
        return

    @wraps(current)
    def apply_live_vwap_truth(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        updated = current(
            records, current_session_raw, current_session_30s_raw, client
        )
        return _augment_progression_records(
            updated, current_session_raw, current_session_30s_raw, client
        )

    _inherit(apply_live_vwap_truth, current)
    apply_live_vwap_truth._gs455_crossover_progression = True
    apply_live_vwap_truth._gs455_original = current
    gs378.apply_live_vwap_truth = apply_live_vwap_truth


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs455_crossover_progression", False):
        calibrated = current
    else:
        original = current

        @wraps(original)
        def calibrated(record: dict) -> dict:
            return _state_with_progression(original, record)

        _inherit(calibrated, current)
        calibrated._gs455_crossover_progression = True
        calibrated._gs455_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_alert_priority() -> None:
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = escalation.escalation_state_changes
    if not getattr(current_changes, "_gs455_crossover_progression", False):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            existing = list(current_changes(rows))
            additions = [
                change for row in rows if (change := _progression_change(row))
            ]
            if not additions:
                return existing
            keys = {
                (
                    str(item.get("symbol") or "").upper(),
                    str(item.get("from") or ""),
                    str(item.get("to") or ""),
                )
                for item in existing
            }
            for change in additions:
                key = (change["symbol"], change["from"], change["to"])
                if key not in keys:
                    existing.append(change)
                    keys.add(key)
            return existing

        _inherit(state_changes, current_changes)
        state_changes._gs455_crossover_progression = True
        state_changes._gs455_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs455_crossover_progression", False):
        @wraps(current_phrase)
        def alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            existing = str(current_phrase(rows) or "")
            progression = _progression_phrase(rows)
            if not progression:
                return existing
            # Existing tier-3 entry urgency always outranks this tier-2 progression pulse.
            if existing and semantic_chime_count(existing) >= 3:
                return existing
            return progression

        _inherit(alert_phrase, current_phrase)
        alert_phrase._gs455_crossover_progression = True
        alert_phrase._gs455_original = current_phrase
        escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install early admission plus ordered crossover-progression operator truth."""
    _install_prefilter()
    _install_progression_evidence()
    _install_state()
    _install_alert_priority()
