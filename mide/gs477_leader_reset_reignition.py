"""GS477: remember proven leaders through a reset and surface re-ignition early.

Sep. 17 live validation exposed a different setup from first-push ignition. SDST had
already made a legitimate expansion, then reset for roughly an hour. At 10:38 ET it
was back near primary VWAP with 30s and 1m SuperTrend bullish, Participation 70.1 and
renewed volume acceleration. At 10:40 it reclaimed primary VWAP while 30s/1m remained
bullish and flow strengthened. Walter had the current evidence, but GS404's reset
memory only looked at the immediately previous pulse, so the earlier leader status
could be forgotten before the constructive reset arrived.

GS477 adds presentation/audio memory only. A current Webull mover that was previously
>5% above VWAP remains a proven leader in a bounded 90-minute memory. If it later
returns to the existing +/-2% near-VWAP window with fresh 30s + 1m bullish structure
and supporting participation/flow, Walter emits RESET WATCH while preserving the
current Opportunity State. If primary VWAP is then reclaimed with 1m also above VWAP,
Walter may render LOOK NOW for chart review. 3m confirmation is additive and gets its
own stronger explanation when Walter's existing 3m evidence turns bullish.

GS477 deliberately does not own ``ui.actionable_candidate_records``. The GS414 final
render boundary enriches a detached snapshot and restores the exact public callable it
received. That preserves GS414's exception-safety contract while still letting the
same enriched snapshot drive visible state. The audio wrapper performs the same
bounded evidence enrichment on its own input, after which established escalation audio
retains priority.

No discovery, market data, indicator formulas, scanner gates, ranking scores,
qualification, readiness, anti-chase, execution or orders change. GS477 never grants
qualified_for_watch/entry/alert and never turns a below-VWAP reset into LOOK NOW.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from time import monotonic
from typing import Any

from .gs375_operator_awareness import awareness_record

PROVEN_LEADER_EXTENSION_PCT = 5.0
NEAR_VWAP_WINDOW_PCT = 2.0
LEADER_MEMORY_TTL_SECONDS = 90 * 60.0
MIN_PARTICIPATION = 20.0
MIN_VOLUME_ACCELERATION = 1.0
MIN_DOLLAR_FLOW_ACCELERATION = 1.25
MAX_REIGNITION_VWAP_DISTANCE_PCT = 5.0

RESET_WATCH = "RESET_WATCH"
REIGNITION = "REIGNITION"
THREE_MINUTE_CONFIRMATION = "THREE_MINUTE_CONFIRMATION"
_PROVENANCE = "PROVEN_LEADER_RESET_REIGNITION"
_STATE_OWNER = "_walter_gs477_leader_reset_state_owner"
_AUDIO_OWNER = "_walter_gs477_leader_reset_audio_owner"


@dataclass
class LeaderMemory:
    extended_at: float
    last_seen_at: float
    max_vwap_distance_pct: float
    peak_pct_change: float | None
    extension_price: float | None
    stage: str = "NONE"
    transition_marker: str | None = None


_leaders: dict[str, LeaderMemory] = {}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _decision(record).get(key, default)


def _timeframes(record: dict) -> dict:
    value = _field(record, "timeframes", {})
    return value if isinstance(value, dict) else {}


def _tf(record: dict, label: str) -> dict:
    detail = _timeframes(record).get(label) or {}
    if not isinstance(detail, dict):
        return {"bullish": False, "above_vwap": False, "available": False}
    bullish = bool(
        detail.get("current_supertrend_bullish")
        if "current_supertrend_bullish" in detail
        else detail.get("supertrend_bullish", detail.get("supertrend"))
    )
    above = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    return {
        "bullish": bullish,
        "above_vwap": above,
        "available": detail.get("data_available") is not False and bool(detail),
    }


def _current_webull_mover(record: dict) -> bool:
    reasons = " | ".join(
        str(value or "") for value in _field(record, "discovery_reasons", []) or []
    )
    return bool(
        "Webull native: day_gainers" in reasons
        or "Webull native: five_minute_movers" in reasons
    )


def _fresh_source(record: dict) -> bool:
    from .gs373_operator_visibility_freshness import MAX_OPERATOR_BAR_AGE_SECONDS

    age = _number(
        _field(
            record,
            "source_bar_age_seconds",
            _field(record, "source_bar_age", _field(record, "bar_age_seconds")),
        )
    )
    return age is not None and 0.0 <= age <= MAX_OPERATOR_BAR_AGE_SECONDS


def _supporting_flow(record: dict) -> tuple[bool, float, float, float]:
    participation = _number(
        _field(record, "participation_score", _field(record, "participation_surge_score", 0.0))
    ) or 0.0
    volume_acceleration = _number(_field(record, "volume_acceleration", 0.0)) or 0.0
    dollar_flow = _number(
        _field(
            record,
            "dollar_flow_acceleration_1m",
            _field(record, "dollar_flow_acceleration", 0.0),
        )
    ) or 0.0
    active = bool(
        participation >= MIN_PARTICIPATION
        and (
            volume_acceleration >= MIN_VOLUME_ACCELERATION
            or dollar_flow >= MIN_DOLLAR_FLOW_ACCELERATION
        )
    )
    return active, participation, volume_acceleration, dollar_flow


def _marker(record: dict) -> str:
    stamp = str(
        _field(
            record,
            "source_bar_timestamp",
            _field(record, "last_bar_timestamp", _field(record, "bar_timestamp", "")),
        )
        or ""
    )
    price = _number(_field(record, "price"))
    return f"{stamp}|{price if price is not None else ''}"


def _remember_extension(record: dict, now: float) -> LeaderMemory | None:
    symbol = str(
        record.get("symbol") or _decision(record).get("symbol") or ""
    ).strip().upper()
    if not symbol:
        return None

    current = _leaders.get(symbol)
    distance = _number(_field(record, "vwap_distance_pct"))
    if (
        distance is not None
        and distance >= PROVEN_LEADER_EXTENSION_PCT
        and _current_webull_mover(record)
        and _fresh_source(record)
    ):
        pct_change = _number(_field(record, "pct_change"))
        price = _number(_field(record, "price"))
        if current is None:
            current = LeaderMemory(
                extended_at=now,
                last_seen_at=now,
                max_vwap_distance_pct=distance,
                peak_pct_change=pct_change,
                extension_price=price,
            )
        else:
            current.extended_at = now
            current.last_seen_at = now
            current.max_vwap_distance_pct = max(current.max_vwap_distance_pct, distance)
            if pct_change is not None:
                current.peak_pct_change = max(current.peak_pct_change or pct_change, pct_change)
            current.extension_price = price or current.extension_price
        _leaders[symbol] = current
    elif current is not None:
        current.last_seen_at = now
    return current


def leader_reset_evidence(record: dict, memory: LeaderMemory | None, *, now: float) -> dict:
    distance = _number(_field(record, "vwap_distance_pct"))
    thirty = _tf(record, "30s")
    one = _tf(record, "1m")
    three = _tf(record, "3m")
    flow, participation, volume_acceleration, dollar_flow = _supporting_flow(record)
    memory_age = (now - memory.extended_at) if memory is not None else None
    memory_fresh = bool(
        memory is not None
        and memory_age is not None
        and 0.0 <= memory_age <= LEADER_MEMORY_TTL_SECONDS
    )
    near_vwap = bool(distance is not None and abs(distance) <= NEAR_VWAP_WINDOW_PCT)
    current_mover = _current_webull_mover(record)
    fresh_source = _fresh_source(record)

    reset_watch = bool(
        memory_fresh
        and near_vwap
        and thirty.get("bullish")
        and thirty.get("above_vwap")
        and one.get("bullish")
        and flow
        and current_mover
        and fresh_source
    )
    reclaimed = bool(
        distance is not None and 0.0 <= distance <= MAX_REIGNITION_VWAP_DISTANCE_PCT
    )
    reignition = bool(reset_watch and reclaimed and one.get("above_vwap"))
    three_confirmed = bool(
        reignition and three.get("bullish") and three.get("above_vwap")
    )
    stage = (
        THREE_MINUTE_CONFIRMATION
        if three_confirmed
        else REIGNITION
        if reignition
        else RESET_WATCH
        if reset_watch
        else "NONE"
    )

    marker = _marker(record)
    stage_fresh = False
    if memory is not None:
        if stage == "NONE":
            memory.stage = "NONE"
            memory.transition_marker = None
        elif stage != memory.stage:
            memory.stage = stage
            memory.transition_marker = marker
            stage_fresh = True
        elif memory.transition_marker == marker:
            # Rendering and audio may inspect the same scan independently.
            stage_fresh = True

    return {
        "active": stage != "NONE",
        "stage": stage,
        "stage_fresh": stage_fresh,
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
        "memory_age_seconds": round(memory_age, 1) if memory_age is not None else None,
        "memory_ttl_seconds": LEADER_MEMORY_TTL_SECONDS,
        "prior_max_vwap_distance_pct": (
            round(memory.max_vwap_distance_pct, 3) if memory is not None else None
        ),
        "prior_peak_pct_change": memory.peak_pct_change if memory is not None else None,
        "current_vwap_distance_pct": distance,
        "near_vwap": near_vwap,
        "vwap_reclaimed": reclaimed,
        "thirty_second_bullish": bool(thirty.get("bullish")),
        "thirty_second_above_vwap": bool(thirty.get("above_vwap")),
        "one_minute_bullish": bool(one.get("bullish")),
        "one_minute_above_vwap": bool(one.get("above_vwap")),
        "three_minute_bullish": bool(three.get("bullish")),
        "three_minute_above_vwap": bool(three.get("above_vwap")),
        "participation_score": round(participation, 1),
        "volume_acceleration": round(volume_acceleration, 2),
        "dollar_flow_acceleration": round(dollar_flow, 2),
        "supporting_flow": flow,
        "current_webull_mover": current_mover,
        "fresh_source": fresh_source,
    }


def apply_leader_reset_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
    """Attach bounded leader-reset evidence without mutating scanner records."""
    now = monotonic() if now is None else now
    output: list[dict] = []

    for record in records or []:
        memory = _remember_extension(record, now)
        evidence = leader_reset_evidence(record, memory, now=now)
        if evidence.get("active"):
            row = deepcopy(record)
            row["leader_reset_reignition"] = evidence
            output.append(row)
        else:
            output.append(record)

    stale = [
        symbol
        for symbol, memory in _leaders.items()
        if now - memory.extended_at > LEADER_MEMORY_TTL_SECONDS
    ]
    for symbol in stale:
        _leaders.pop(symbol, None)
    return output


def augment_leader_reset_records(records: list[dict], visible: list[dict]) -> list[dict]:
    """Keep an active reset/re-ignition visible as awareness only when needed."""
    output = list(visible or [])
    present = {
        str(record.get("symbol") or "").strip().upper()
        for record in output
        if str(record.get("symbol") or "").strip()
    }
    for record in records or []:
        evidence = record.get("leader_reset_reignition") or {}
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present or not evidence.get("active"):
            continue
        output.append(awareness_record(record))
        present.add(symbol)
    return output


def enrich_visible_records(records: list[dict], actionable_function) -> list[dict]:
    """Enrich a detached render snapshot without replacing the public UI callable."""
    enriched = apply_leader_reset_marks(records)
    visible = list(actionable_function(enriched) or [])
    return augment_leader_reset_records(enriched, visible)


def leader_reset_opportunity_state(original, record: dict) -> dict:
    """Turn a confirmed reset reclaim into LOOK NOW; below VWAP remains a watch."""
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    evidence = record.get("leader_reset_reignition") or {}
    stage = str(evidence.get("stage") or "NONE")
    if stage == "NONE" or base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance
    view["leader_reset_reignition"] = evidence

    distance = _number(evidence.get("current_vwap_distance_pct"))
    if stage == RESET_WATCH:
        prior = float(evidence.get("prior_max_vwap_distance_pct") or 0.0)
        current = abs(float(distance or 0.0))
        view["reason"] = (
            f"LEADER RESET WATCH: this mover was previously {prior:.1f}%+ above VWAP and "
            f"has reset to within {current:.1f}% of VWAP. 30s and 1m SuperTrend are bullish "
            "with participation/flow active."
        )
        view["next_step"] = (
            "Keep the chart open. Wait for primary VWAP reclaim; 3m SuperTrend confirmation "
            "adds ignition strength. This is attention only, not entry authority."
        )
        return view

    if distance is None or distance < 0.0 or distance > MAX_REIGNITION_VWAP_DISTANCE_PCT:
        return view
    if base.get("state") == unified.CHASE_WAIT:
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    if stage == THREE_MINUTE_CONFIRMATION:
        view["reason"] = (
            "LEADER RE-IGNITION: primary VWAP is reclaimed after a constructive reset; "
            "30s, 1m and 3m SuperTrend are now bullish with participation/flow active."
        )
        view["next_step"] = (
            "Open the chart now. The 3m ignition rung has joined, but normal readiness, "
            "anti-chase and execution rules remain authoritative."
        )
    else:
        view["reason"] = (
            "LEADER RE-IGNITION: primary VWAP is reclaimed after a constructive reset; "
            "30s and 1m SuperTrend are bullish with participation/flow active. 3m is not "
            "yet confirmed by Walter's current evidence."
        )
        view["next_step"] = (
            "Open the chart now and watch the 3m SuperTrend rung. This is chart-review "
            "authority only; normal readiness, anti-chase and execution rules remain."
        )
    return view


def leader_reset_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh reset transition without implying a trade instruction."""
    for record in records or []:
        evidence = record.get("leader_reset_reignition") or {}
        if not evidence.get("stage_fresh"):
            continue
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        stage = evidence.get("stage")
        if stage == RESET_WATCH:
            distance = abs(float(evidence.get("current_vwap_distance_pct") or 0.0))
            return (
                f"{symbol}. RESET WATCH. Proven leader is back within {distance:.1f} percent "
                "of VWAP with 30 second and 1 minute SuperTrend bullish. Watch the reclaim. "
                "Attention only."
            )
        if stage == THREE_MINUTE_CONFIRMATION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed and the 3 minute "
                "SuperTrend rung is confirmed. Attention only; entry is not authorized by this cue."
            )
        if stage == REIGNITION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed with 30 second and "
                "1 minute SuperTrend bullish and active flow. 3 minute confirmation pending."
            )
    return ""


def reset_leader_memory() -> None:
    _leaders.clear()


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _STATE_OWNER, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return leader_reset_opportunity_state(current, record)

        _inherit(calibrated, current)
        calibrated._gs477_leader_reset_reignition = True
        calibrated._gs477_original = current
        setattr(calibrated, _STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_audio() -> None:
    from . import escalation

    current = escalation.escalation_alert_phrase
    if getattr(current, _AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        # Update bounded leader memory even when an established alert has priority.
        enriched = apply_leader_reset_marks(records)
        established = current(records)
        if established:
            return established
        return leader_reset_audio_phrase(enriched)

    _inherit(alert_phrase, current)
    alert_phrase._gs477_leader_reset_reignition = True
    alert_phrase._gs477_original = current
    setattr(alert_phrase, _AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install state/audio only; GS414 owns detached record enrichment/restoration."""
    _install_state()
    _install_audio()
