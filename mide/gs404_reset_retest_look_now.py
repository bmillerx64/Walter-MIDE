"""GS404: surface a near-VWAP retest after a freshly extended move.

Live ZTG validation on 2026-09-09 exposed a narrow operator-attention gap. Walter
already had the symbol from current Webull radar, but after an extended first push
it reset back to VWAP while 1m SuperTrend remained bullish and participation/flow
were still active. The scanner correctly withheld entry authority, yet the
trader-facing workflow did not produce a timely LOOK NOW before price re-extended.

This layer is presentation/attention only. It does not change discovery, scanner
qualification, trigger/readiness thresholds, ranking, VWAP/ST evidence, execution,
or orders. It reuses existing boundaries:
* GS305's >5% VWAP extension as evidence that a real reset occurred;
* GS373/GS393's +/-2% near-VWAP operator window;
* GS393's existing participation/flow support thresholds;
* current Webull day-gainer or five-minute-mover provenance.

The result is chart-review authority only: LOOK NOW. Entry and alert qualification
fields on any injected awareness copy remain false. GS398/GS402 may still provide
the dedicated LOOK NOW browser tone because that sound represents operator attention,
not trade authorization.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable

from .gs375_operator_awareness import AWARENESS_ONLY_KEY, awareness_record

RESET_RETEST_KEY = "operator_reset_retest_look_now"
RESET_RETEST_PROVENANCE = "RESET_RETEST_NEAR_VWAP"

# Existing Gold Standard boundaries, reused rather than creating entry thresholds.
PREVIOUS_EXTENSION_MIN_PCT = 5.0
NEAR_VWAP_WINDOW_PCT = 2.0
MIN_PARTICIPATION = 20.0
MIN_VOLUME_ACCELERATION = 1.0
MIN_DOLLAR_FLOW_ACCELERATION = 1.25

WEBULL_DAY_GAINER_REASON = "Webull native: day_gainers"
WEBULL_FIVE_MINUTE_REASON = "Webull native: five_minute_movers"


def _market_evidence():
    from mide.authorities import market_evidence

    return market_evidence


def _thesis_state():
    from mide.authorities import thesis_state

    return thesis_state


def _presentation_audio():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    current = getattr(
        _market_evidence(),
        "reset_retest_number",
        None,
    )
    if callable(current):
        return current(
            record,
            *keys,
            default=default,
        )
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _one_minute(record: dict) -> dict:
    current = getattr(
        _market_evidence(),
        "reset_retest_one_minute",
        None,
    )
    if callable(current):
        return current(record)
    states = record.get("timeframes") or {}
    value = states.get("1m") if isinstance(states, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _current_webull_radar_attention(record: dict) -> bool:
    current = getattr(
        _market_evidence(),
        "reset_retest_current_webull_radar_attention",
        None,
    )
    if callable(current):
        return bool(current(record))
    reasons = " | ".join(str(value or "") for value in record.get("discovery_reasons") or [])
    return WEBULL_DAY_GAINER_REASON in reasons or WEBULL_FIVE_MINUTE_REASON in reasons


def _fresh_source(record: dict) -> bool:
    current = getattr(
        _market_evidence(),
        "reset_retest_fresh_source",
        None,
    )
    if callable(current):
        return bool(current(record))
    from .gs373_operator_visibility_freshness import MAX_OPERATOR_BAR_AGE_SECONDS

    age = _number(record, "source_bar_age_seconds", "source_bar_age", "bar_age_seconds")
    return age is not None and 0.0 <= age <= MAX_OPERATOR_BAR_AGE_SECONDS


def reset_retest_attention_evidence(record: dict) -> dict:
    """Warm-deploy-safe facade for authoritative reset/retest market evidence."""
    current = getattr(
        _market_evidence(),
        "reset_retest_attention_evidence",
        None,
    )
    if callable(current):
        return current(record)

    # Retained-runtime fallback for an older Market Evidence generation.
    previous = record.get("opportunity_pulse_previous") or {}
    continuity = bool(previous)

    previous_distance = _number(previous, "vwap_distance_pct")
    current_distance = _number(record, "vwap_distance_pct")
    previous_extended = bool(
        previous_distance is not None and previous_distance > PREVIOUS_EXTENSION_MIN_PCT
    )
    near_vwap_now = bool(
        current_distance is not None and abs(current_distance) <= NEAR_VWAP_WINDOW_PCT
    )

    one = _one_minute(record)
    one_minute_bullish = bool(one.get("supertrend"))

    participation = _number(
        record, "participation_score", "participation_surge_score", default=0.0
    ) or 0.0
    volume_acceleration = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _number(
        record,
        "dollar_flow_acceleration_1m",
        "dollar_flow_acceleration",
        default=0.0,
    ) or 0.0

    participation_present = participation >= MIN_PARTICIPATION
    flow_present = bool(
        volume_acceleration >= MIN_VOLUME_ACCELERATION
        or dollar_flow >= MIN_DOLLAR_FLOW_ACCELERATION
    )
    current_radar_attention = _current_webull_radar_attention(record)
    fresh_source = _fresh_source(record)

    recent = bool(
        continuity
        and previous_extended
        and near_vwap_now
        and one_minute_bullish
        and participation_present
        and flow_present
        and current_radar_attention
        and fresh_source
    )
    return {
        "recent": recent,
        "trigger": "RESET_RETEST_NEAR_VWAP" if recent else None,
        "chart_review_only": True,
        "entry_authority_unchanged": True,
        "continuity": continuity,
        "previous_vwap_distance_pct": previous_distance,
        "previous_extended": previous_extended,
        "current_vwap_distance_pct": current_distance,
        "near_vwap_now": near_vwap_now,
        "one_minute_supertrend_bullish": one_minute_bullish,
        "participation_score": round(float(participation), 1),
        "participation_present": participation_present,
        "volume_acceleration": round(float(volume_acceleration), 2),
        "dollar_flow_acceleration": round(float(dollar_flow), 2),
        "flow_present": flow_present,
        "current_webull_radar_attention": current_radar_attention,
        "fresh_source": fresh_source,
    }


def reset_retest_eligible(record: dict) -> bool:
    current = getattr(
        _market_evidence(),
        "reset_retest_eligible",
        None,
    )
    if callable(current):
        return bool(current(record))
    return bool(reset_retest_attention_evidence(record)["recent"])


def _tag_awareness_copy(record: dict) -> dict:
    current = getattr(
        _presentation_audio(),
        "reset_retest_awareness_copy",
        None,
    )
    if callable(current):
        return current(record)

    # Retained-runtime fallback for an older Presentation + Audio generation.
    row = awareness_record(record)
    row[RESET_RETEST_KEY] = True
    return row


def augment_reset_retest_records(records: list[dict], visible: list[dict]) -> list[dict]:
    """Warm-deploy-safe facade for reset/retest visible-record awareness."""
    current = getattr(
        _presentation_audio(),
        "augment_reset_retest_visible_records",
        None,
    )
    if callable(current):
        return current(
            records,
            visible,
        )

    # Retained-runtime fallback for an older Presentation + Audio generation.
    output: list[dict] = []
    present: set[str] = set()

    for record in visible or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present:
            continue
        if reset_retest_eligible(record):
            tagged = deepcopy(record)
            tagged[RESET_RETEST_KEY] = True
            output.append(tagged)
        else:
            output.append(record)
        present.add(symbol)

    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present or not reset_retest_eligible(record):
            continue
        output.append(_tag_awareness_copy(record))
        present.add(symbol)
    return output


def reset_retest_opportunity_state(
    record: dict,
    state_function: Callable[[dict], dict] | None = None,
) -> dict:
    """Warm-deploy-safe facade for authoritative reset/retest state meaning."""
    from . import gs310_unified_opportunity_state as unified

    original = state_function or getattr(
        unified.opportunity_state,
        "_gs404_original",
        unified.opportunity_state,
    )
    current = getattr(
        _thesis_state(),
        "reset_retest_opportunity_state",
        None,
    )
    if callable(current):
        return current(
            original,
            record,
        )

    # Retained-runtime fallback for an older Thesis / State generation.
    view = deepcopy(original(record))
    evidence = reset_retest_attention_evidence(record)
    if not evidence["recent"]:
        return view

    if view.get("state") in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = (
        "Reset/retest: a current Webull mover returned to the near-VWAP window after "
        "extension while 1m SuperTrend remains bullish and participation/flow persist."
    )
    view["next_step"] = (
        "Open the chart now and evaluate the retest. This is investigation only; "
        "Walter's normal entry/readiness and anti-chase rules remain authoritative."
    )
    provenance = list(view.get("attention_provenance") or [])
    if RESET_RETEST_PROVENANCE not in provenance:
        provenance.append(RESET_RETEST_PROVENANCE)
    view["attention_provenance"] = provenance
    view["reset_retest_attention"] = evidence
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after GS401 as the final narrow live-attention correction."""
    from . import ui

    current_records = ui.actionable_candidate_records
    if not getattr(current_records, "_gs404_reset_retest", False):
        original_records = current_records

        def operator_records(records: list[dict]) -> list[dict]:
            return augment_reset_retest_records(records, original_records(records))

        _inherit(operator_records, original_records)
        operator_records._gs404_reset_retest = True
        operator_records._gs404_original = original_records
        ui.actionable_candidate_records = operator_records

    authority = getattr(
        _thesis_state(),
        "install_reset_retest_state",
        None,
    )
    if callable(authority):
        authority()
        return

    # Retained-runtime fallback for an older Thesis / State generation.
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current_state = unified.opportunity_state
    if not getattr(current_state, "_gs404_reset_retest", False):
        original_state = current_state

        def retest_state(record: dict) -> dict:
            return reset_retest_opportunity_state(record, original_state)

        _inherit(retest_state, original_state)
        retest_state._gs404_reset_retest = True
        retest_state._gs404_original = original_state
        unified.opportunity_state = retest_state
    else:
        retest_state = current_state

    voice.opportunity_state = retest_state
    consistency.opportunity_state = retest_state
    hierarchy.opportunity_state = retest_state
