"""GS473: make a fresh multi-timeframe WATCH NOW audible without granting entry.

Sep. 16 live LESL evidence exposed an operator-attention/audio mismatch rather than a
scanner miss. Walter first saw LESL near 0.557 (+19.3%) with Participation and
Structure both passed, 1m/3m/5m bullish above VWAP, ``candidate_status=Entry Ready``
and trader-facing ``status=WATCH NOW``. The executable alert flag was false because
LESL was already 9.6% above VWAP, lacked a ready trigger/catalyst, and correctly failed
entry authorization. The screen therefore had useful attention evidence while the
audible path stayed silent.

GS473 separates those jobs. Existing escalation/entry audio keeps priority. Only when
that path is silent, a *fresh* WATCH NOW / Entry Ready attention observation may speak
LOOK NOW when the already-computed participation + structure gates pass and either:
- 30s -> 1m -> 3m are currently bullish above VWAP, or
- 1m -> 3m -> 5m are currently bullish above VWAP.

The second path deliberately lets Walter remain useful while the genuine 30s Webull
stream is being repaired; it is not a synthetic 30s substitute. A compact previous
record already preserves status/candidate_status, so the same continuous WATCH NOW is
not announced every 60-second scan. If the setup is extended, the phrase explicitly
says DO NOT CHASE. ``qualified_for_entry`` and ``qualified_for_alert`` are never
changed.

Presentation/audio only: no discovery, market-data request/value, indicator formula,
score, ranking, threshold, participation/structure decision, qualification, readiness,
execution, session authority, or order behavior changes.
"""
from __future__ import annotations

from functools import wraps
from typing import Any


_OWNER = "_walter_gs473_operator_attention_audio_owner"
ATTENTION_STATUS = "WATCH NOW"
ATTENTION_CANDIDATE = "ENTRY READY"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
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
        _normalized(_field(record, "status")) == ATTENTION_STATUS
        or _normalized(_field(record, "candidate_status")) == ATTENTION_CANDIDATE
    )


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


def _supportive(record: dict, label: str) -> bool:
    detail = _timeframes(record).get(label) or {}
    if not isinstance(detail, dict) or detail.get("data_available") is False:
        return False
    bullish = bool(
        detail.get("current_supertrend_bullish")
        if "current_supertrend_bullish" in detail
        else detail.get("supertrend")
    )
    above = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    return bool(bullish and above)


def _cascade(record: dict) -> tuple[str, ...]:
    if all(_supportive(record, label) for label in ("30s", "1m", "3m")):
        return ("30s", "1m", "3m")
    if all(_supportive(record, label) for label in ("1m", "3m", "5m")):
        return ("1m", "3m", "5m")
    return ()


def _previous_already_attention(record: dict) -> bool:
    previous = record.get("opportunity_pulse_previous") or {}
    if not isinstance(previous, dict) or not previous:
        return False
    return _attention_label(previous)


def operator_attention_candidate(record: dict) -> dict:
    """Return presentation-only LOOK NOW truth from already-computed evidence."""
    cascade = _cascade(record)
    active = bool(
        _attention_label(record)
        and _gate_passed(record, "participation_gate")
        and _gate_passed(record, "structure_gate")
        and cascade
    )
    fresh = bool(active and not _previous_already_attention(record))
    distance = _number(_field(record, "vwap_distance_pct"))
    return {
        "active": active,
        "fresh": fresh,
        "symbol": str(record.get("symbol") or _decision(record).get("symbol") or "").upper(),
        "cascade": list(cascade),
        "vwap_distance_pct": distance,
        "qualified_for_entry": bool(record.get("qualified_for_entry") is True),
        "qualified_for_alert": bool(record.get("qualified_for_alert") is True),
        "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }


def _cascade_phrase(labels: list[str]) -> str:
    if not labels:
        return "multi-timeframe structure is bullish above VWAP"
    if len(labels) == 1:
        joined = labels[0]
    elif len(labels) == 2:
        joined = f"{labels[0]} and {labels[1]}"
    else:
        joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    return f"{joined} are bullish above VWAP"


def operator_attention_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh operator cue; never imply executable entry authorization."""
    candidates = []
    for record in records or []:
        detail = operator_attention_candidate(record)
        if detail.get("fresh") and detail.get("symbol"):
            candidates.append((record, detail))
    if not candidates:
        return ""

    # Preserve incoming operator order. The first row is already Walter's highest
    # presentation priority, so this audio layer invents no new score or ranking.
    record, detail = candidates[0]
    symbol = detail["symbol"]
    phrase = f"{symbol}. LOOK NOW. {_cascade_phrase(detail['cascade'])}."
    distance = detail.get("vwap_distance_pct")
    if distance is not None and distance > 5.0:
        phrase += f" Extended {distance:.1f} percent above VWAP. Do not chase; watch for a reset."
    elif not detail.get("qualified_for_alert"):
        phrase += " Attention only; entry is not authorized yet."
    return phrase


def install() -> None:
    """Install outside the existing escalation phrase while preserving its priority."""
    from . import escalation

    current = escalation.escalation_alert_phrase
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def escalation_alert_phrase(records: list[dict]) -> str:
        established = current(records)
        if established:
            return established
        return operator_attention_audio_phrase(records)

    escalation_alert_phrase._gs473_operator_attention_audio = True
    escalation_alert_phrase._gs473_original = current
    setattr(escalation_alert_phrase, _OWNER, True)
    escalation.escalation_alert_phrase = escalation_alert_phrase
