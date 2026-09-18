"""GS492: make bottom-up runner maturation itself audible.

Sep. 18 live NCPL/QNME/MRNO validation exposed an audio-freshness bug rather than a
market-data miss. NCPL entered WATCH NOW with 30s+1m aligned; one scan later 3m joined,
participation stayed near 70 and volume acceleration jumped above 6x. GS473 remained
silent at the important 3m join because its freshness test only asked whether the prior
scan was already WATCH NOW.

GS492 separates status freshness from structure freshness:
* RUNNER BUILDING: a newly elevated WATCH NOW/ENTRY READY observation has current
  30s+1m bullish-above-VWAP structure with both established gates passed.
* RUNNER DETECTED: 30s+1m+3m are bullish above VWAP and the 3m bullish flip or current
  30s/1m ST/VWAP cross is fresh. This event remains audible even if WATCH NOW already
  existed on the immediately prior scan.

The phrase deliberately contains LOOK NOW so Walter's existing tier-2 browser cadence
remains the distinctive operator-attention sound. If price is >5% above VWAP, Walter
explicitly says not to chase and to watch for a reset.

Presentation/audio only. No discovery, market-data values, indicator formulas, scores,
ranking, gates, qualification, readiness, anti-chase, execution, or orders change.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

_OWNER = "_walter_gs492_maturation_transition_audio"
FRESH_3M_SECONDS = 180.0


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


def _normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _attention_label(record: dict) -> bool:
    return bool(
        _normalized(_field(record, "status")) == "WATCH NOW"
        or _normalized(_field(record, "candidate_status")) == "ENTRY READY"
    )


def _previous_attention(record: dict) -> bool:
    previous = record.get("opportunity_pulse_previous") or {}
    return isinstance(previous, dict) and bool(previous) and _attention_label(previous)


def _gate_passed(record: dict, name: str) -> bool:
    value = record.get(name)
    if not isinstance(value, dict):
        value = _decision(record).get(name) or {}
    return isinstance(value, dict) and value.get("passed") is True


def _timeframes(record: dict) -> dict:
    value = record.get("timeframes")
    if not isinstance(value, dict):
        value = _decision(record).get("timeframes") or {}
    return value if isinstance(value, dict) else {}


def _tf(record: dict, label: str) -> dict:
    detail = _timeframes(record).get(label) or {}
    if not isinstance(detail, dict):
        return {}
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
        "raw": detail,
        "supportive": bool(
            detail.get("data_available") is not False and bullish and above
        ),
        "bullish": bullish,
        "above_vwap": above,
    }


def _cross_new(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    cross = raw.get("st_vwap_line_cross") or {}
    return isinstance(cross, dict) and cross.get("new") is True


def _three_minute_fresh(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    age = _number(raw.get("bullish_flip_age_seconds"))
    return bool(age is not None and 0.0 <= age <= FRESH_3M_SECONDS)


def maturation_transition(record: dict) -> dict:
    thirty = _tf(record, "30s")
    one = _tf(record, "1m")
    three = _tf(record, "3m")
    gates = bool(
        _gate_passed(record, "participation_gate")
        and _gate_passed(record, "structure_gate")
    )
    two_rung = bool(thirty.get("supportive") and one.get("supportive"))
    three_rung = bool(two_rung and three.get("supportive"))
    structure_fresh = bool(
        _three_minute_fresh(three)
        or _cross_new(thirty)
        or _cross_new(one)
    )

    stage = "NONE"
    if gates and three_rung and structure_fresh:
        stage = "RUNNER_DETECTED"
    elif gates and two_rung and _attention_label(record) and not _previous_attention(record):
        stage = "RUNNER_BUILDING"

    return {
        "active": stage != "NONE",
        "stage": stage,
        "symbol": str(record.get("symbol") or _decision(record).get("symbol") or "").strip().upper(),
        "gates_passed": gates,
        "thirty_second_supportive": bool(thirty.get("supportive")),
        "one_minute_supportive": bool(one.get("supportive")),
        "three_minute_supportive": bool(three.get("supportive")),
        "structure_fresh": structure_fresh,
        "vwap_distance_pct": _number(_field(record, "vwap_distance_pct")),
        "qualified_for_entry": bool(_field(record, "qualified_for_entry") is True),
        "qualified_for_alert": bool(_field(record, "qualified_for_alert") is True),
        "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }


def maturation_audio_phrase(records: list[dict]) -> str:
    for record in records or []:
        event = maturation_transition(record)
        if not event.get("active") or not event.get("symbol"):
            continue
        symbol = event["symbol"]
        if event["stage"] == "RUNNER_DETECTED":
            phrase = (
                f"{symbol}. RUNNER DETECTED. LOOK NOW. "
                "30 second, 1 minute, and 3 minute structure are aligned above VWAP."
            )
        else:
            phrase = (
                f"{symbol}. RUNNER BUILDING. LOOK NOW. "
                "30 second and 1 minute structure are aligned; 3 minute confirmation is pending."
            )
        distance = event.get("vwap_distance_pct")
        if distance is not None and distance > 5.0:
            phrase += (
                f" Extended {distance:.1f} percent above VWAP. "
                "Do not chase; watch for a reset."
            )
        else:
            phrase += " Attention only; normal entry rules still apply."
        return phrase
    return ""


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Put maturation-event audio above routine/tier-2 cues but below tier-3 entry."""
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current = escalation.escalation_alert_phrase
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        established = current(rows)
        if established and semantic_chime_count(established) >= 3:
            return established
        maturation = maturation_audio_phrase(rows)
        return maturation or established

    _inherit(alert_phrase, current)
    alert_phrase._gs492_maturation_transition_audio = True
    alert_phrase._gs492_original = current
    setattr(alert_phrase, _OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase
