"""GS527: surface exceptional fresh 30s flow bursts before 1m confirmation.

Sept. 22 LHSW live evidence exposed an operator-attention gap. Around the user's ZEO
entry, LHSW had a fresh bullish 30s SuperTrend flip with roughly 4.7x 30s volume
acceleration and 5x dollar-flow acceleration, but 1m/3m had not yet repaired. GS462
correctly withheld its 30s->1m EARLY WATCH because 1m was not supportive, but that
also made the unusually strong first ignition cue too easy to miss.

GS527 adds a bounded presentation-only EARLY SURGE WATCH:
* canonical 30s bullish flip age <= 90 seconds;
* 30s price is above 30s VWAP;
* 30s volume acceleration >= 3x;
* 30s dollar-flow acceleration >= 3x.

The event does not change the canonical Opportunity State, qualification, readiness,
anti-chase, retest, Mission Rank, execution, or orders. It only:
* annotates the card with explicit early-surge context;
* lifts the fresh event above ordinary Mission-Rank peers but below WATCH FOR ENTRY
  and established fresh multi-timeframe maturation; and
* permits one attention-only spoken cue when higher-tier audio is otherwise absent.

This is deliberately an observation-before-confirmation cue. 1m/3m confirmation is
still required by the established entry architecture.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

FRESH_BURST_SECONDS = 90.0
MIN_VOLUME_ACCELERATION_30S = 3.0
MIN_DOLLAR_FLOW_ACCELERATION_30S = 3.0
_PROVENANCE = "GS527_EXPLOSIVE_30S_SURGE"
_STATE_OWNER = "_walter_gs527_explosive_30s_surge_state_owner"
_ORDER_OWNER = "_walter_gs527_explosive_30s_surge_order_owner"
_AUDIO_OWNER = "_walter_gs527_explosive_30s_surge_audio_owner"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def explosive_30s_surge(record: dict) -> dict:
    """Return bounded attention truth from already-computed 30s tripwire evidence."""
    from . import gs462_preflip_ignition_watch as gs462

    thirty = gs462._timeframe_detail(record, "30s")
    age = _number(thirty.get("flip_age_seconds"))
    volume = _number(record.get("volume_acceleration_30s"))
    dollar = _number(record.get("dollar_flow_acceleration_30s"))

    active = bool(
        thirty.get("bullish")
        and thirty.get("above_vwap")
        and age is not None
        and 0.0 <= age <= FRESH_BURST_SECONDS
        and volume is not None
        and volume >= MIN_VOLUME_ACCELERATION_30S
        and dollar is not None
        and dollar >= MIN_DOLLAR_FLOW_ACCELERATION_30S
    )
    return {
        "active": active,
        "symbol": str(record.get("symbol") or "").strip().upper(),
        "flip_age_seconds": age,
        "volume_acceleration_30s": volume,
        "dollar_flow_acceleration_30s": dollar,
        "thirty_second_above_vwap": bool(thirty.get("above_vwap")),
        "thirty_second_bullish": bool(thirty.get("bullish")),
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
        "qualification_authority_changed": False,
        "readiness_authority_changed": False,
    }


def state_with_explosive_30s(original, record: dict) -> dict:
    """Annotate the existing state; never promote it."""
    from . import gs310_unified_opportunity_state as unified

    view = original(record)
    event = explosive_30s_surge(record)
    if not event.get("active") or view.get("state") == unified.HALTED:
        return view

    result = deepcopy(view)
    provenance = list(result.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    result["attention_provenance"] = provenance
    result["explosive_30s_surge"] = event

    volume = event["volume_acceleration_30s"]
    dollar = event["dollar_flow_acceleration_30s"]
    age = event["flip_age_seconds"]
    surge_text = (
        f"EARLY SURGE WATCH: fresh 30s bullish flip ({age:.0f}s old) with "
        f"{volume:.1f}x volume and {dollar:.1f}x dollar-flow acceleration."
    )
    reason = str(result.get("reason") or "").strip()
    if "EARLY SURGE WATCH:" not in reason:
        result["reason"] = f"{surge_text} {reason}".strip()

    next_step = str(result.get("next_step") or "").strip()
    discipline = (
        "Open the chart now for observation, but do not treat this as entry authority. "
        "1m/3m confirmation, existing VWAP guards, readiness and execution rules remain authoritative."
    )
    if discipline not in next_step:
        result["next_step"] = f"{discipline} {next_step}".strip()
    return result


def _attention_band(record: dict) -> int:
    """Final event ordering: entry > fresh maturation > explosive 30s > baseline."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs517_fresh_event_priority as gs517

    try:
        state = str(unified.opportunity_state(record).get("state") or "")
    except Exception:
        state = ""
    if state == unified.WATCH_FOR_ENTRY:
        return 4
    if state == unified.HALTED:
        return 0
    if gs517.fresh_maturation_event(record):
        return 3
    if explosive_30s_surge(record).get("active"):
        return 2
    return 1


def ordered_explosive_30s_records(records: list[dict], baseline_order=None) -> list[dict]:
    """Stable event lift over the established GS517/Mission-Rank order."""
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    rows.sort(key=_attention_band, reverse=True)
    return rows


def explosive_30s_audio_phrase(records: list[dict]) -> str:
    """Speak one attention-only surge cue without manufacturing LOOK NOW/ENTRY READY."""
    for record in records or []:
        event = explosive_30s_surge(record)
        if not event.get("active") or not event.get("symbol"):
            continue
        return (
            f"{event['symbol']}. EARLY SURGE WATCH. Fresh 30 second bullish flip with "
            f"{event['volume_acceleration_30s']:.1f} times volume and "
            f"{event['dollar_flow_acceleration_30s']:.1f} times dollar flow. "
            "One minute confirmation is still pending. Attention only."
        )
    return ""


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
            return state_with_explosive_30s(current, record)

        _inherit(calibrated, current)
        calibrated._gs527_explosive_30s_surge_watch = True
        calibrated._gs527_original = current
        setattr(calibrated, _STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_order() -> None:
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _ORDER_OWNER, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_explosive_30s_records(records, baseline_order=current)

    _inherit(ordered_escalation_records, current)
    ordered_escalation_records._gs527_explosive_30s_surge_watch = True
    ordered_escalation_records._gs527_original = current
    setattr(ordered_escalation_records, _ORDER_OWNER, True)
    gs369.ordered_escalation_records = ordered_escalation_records


def _install_audio() -> None:
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current = escalation.escalation_alert_phrase
    if getattr(current, _AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        established = current(rows)
        # Preserve existing LOOK NOW / WATCH NOW and entry-urgency audio.
        if established and semantic_chime_count(established) >= 2:
            return established
        burst = explosive_30s_audio_phrase(rows)
        return burst or established

    _inherit(alert_phrase, current)
    alert_phrase._gs527_explosive_30s_surge_watch = True
    alert_phrase._gs527_original = current
    setattr(alert_phrase, _AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install after GS526 at the final presentation/audio boundary."""
    _install_state()
    _install_order()
    _install_audio()
