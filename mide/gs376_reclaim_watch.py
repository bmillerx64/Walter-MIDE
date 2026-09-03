"""GS376: surface fresh leader reconstruction before ordinary DEVELOPING/CHASE noise.

Live validation on 2026-09-03 exposed a second-act attention gap.  Walter could
correctly suppress stale/far-below names (GS373) and keep current DAY_GAINERS
visible without granting trade authority (GS375), yet a major morning leader that
flushed and then began rebuilding on SuperTrend/VWAP could still disappear behind
already-extended CHASE / WAIT names.

GS376 adds one trader-facing state only: ``RECLAIM WATCH``.  It is deliberately
below LOOK NOW and above ordinary DEVELOPING.  The state is reserved for a current
Webull top mover with prior-scan continuity, fresh source data, a meaningful reset
toward VWAP, and a fresh bullish SuperTrend recovery.  A narrow reconstruction
exception may keep the symbol visible as far as 5% below VWAP; this does *not*
restore the broad far-below visibility removed by GS373.

No discovery, scoring, ranking, watch/entry qualification, trigger thresholds,
readiness, alerts' underlying evidence, execution, or orders are changed.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable

from .gs375_operator_awareness import AWARENESS_ONLY_KEY, awareness_record

RECLAIM_WATCH = "RECLAIM WATCH"
RECLAIM_WATCH_KEY = "operator_reclaim_watch"

# Reuse established boundaries rather than creating an entry rule.  GS310 treats
# +2% as the upper edge of the near-VWAP presentation window; GS305 already treats
# >5% extension as a reset/chase condition.  GS376 uses the symmetric 5% downside
# only for this strict, fresh reconstruction-attention exception.
MAX_RECLAIM_ABOVE_VWAP_PCT = 2.0
MAX_RECLAIM_BELOW_VWAP_PCT = 5.0
MAJOR_MOVER_MIN_PCT = 20.0


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _fresh_source_bar(record: dict) -> bool:
    """Require explicit current market evidence for the reconstruction exception."""
    from .gs373_operator_visibility_freshness import MAX_OPERATOR_BAR_AGE_SECONDS

    age = _number(record, "source_bar_age_seconds", "source_bar_age", "bar_age_seconds")
    return age is not None and 0.0 <= age <= MAX_OPERATOR_BAR_AGE_SECONDS


def _fresh_supertrend_recovery(record: dict, previous: dict) -> bool:
    """Reuse Walter's existing 10-minute SuperTrend freshness contract."""
    from .scanner_v2 import TRIGGER_ST_MAX_AGE_SECONDS

    fresh_flip = bool(record.get("supertrend_30s_flip", record.get("supertrend_flip")))
    age = _number(
        record,
        "supertrend_30s_flip_age_seconds",
        "supertrend_flip_age_seconds",
    )
    if fresh_flip and (age is None or age <= TRIGGER_ST_MAX_AGE_SECONDS):
        return True

    current_bullish = bool(record.get("supertrend_bullish"))
    previous_bullish = bool(previous.get("supertrend_bullish"))
    return current_bullish and not previous_bullish


def _vwap_reconstruction(record: dict, previous: dict) -> bool:
    """Require evidence that the reset is moving back toward usable structure."""
    relation = str(record.get("vwap_relation") or "").lower()
    previous_relation = str(previous.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    previous_distance = _number(previous, "vwap_distance_pct")

    if distance is not None:
        if distance < -MAX_RECLAIM_BELOW_VWAP_PCT or distance > MAX_RECLAIM_ABOVE_VWAP_PCT:
            return False
    elif relation not in {"above", "testing"}:
        return False

    if relation == "above" and previous_relation != "above":
        return True
    if relation == "testing" and previous_relation == "below":
        return True
    if distance is not None and previous_distance is not None:
        return abs(distance) < abs(previous_distance)
    return False


def reclaim_watch_evaluation(record: dict) -> dict:
    """Describe a fresh second-act reconstruction using existing live evidence."""
    from .gs309_current_attention_mission import current_attention_provenance

    previous = record.get("opportunity_pulse_previous") or {}
    provenance = tuple(current_attention_provenance(record))
    pct_change = _number(record, "pct_change", "percent_change") or 0.0
    distance = _number(record, "vwap_distance_pct")

    current_top_mover = "WEBULL_TOP_MOVER" in provenance
    continuity = bool(previous)
    fresh_bar = _fresh_source_bar(record)
    major_mover = pct_change >= MAJOR_MOVER_MIN_PCT
    trend_recovery = _fresh_supertrend_recovery(record, previous) if continuity else False
    vwap_reconstruction = _vwap_reconstruction(record, previous) if continuity else False

    eligible = bool(
        current_top_mover
        and continuity
        and fresh_bar
        and major_mover
        and trend_recovery
        and vwap_reconstruction
    )
    return {
        "eligible": eligible,
        "current_top_mover": current_top_mover,
        "continuity": continuity,
        "fresh_bar": fresh_bar,
        "major_mover": major_mover,
        "trend_recovery": trend_recovery,
        "vwap_reconstruction": vwap_reconstruction,
        "pct_change": round(pct_change, 2),
        "vwap_distance_pct": round(distance, 2) if distance is not None else None,
        "attention_provenance": list(provenance),
    }


def reclaim_watch_eligible(record: dict) -> bool:
    return bool(reclaim_watch_evaluation(record)["eligible"])


def _tag_reclaim_copy(record: dict, *, awareness_only: bool) -> dict:
    row = awareness_record(record) if awareness_only else deepcopy(record)
    row[RECLAIM_WATCH_KEY] = True
    return row


def augment_reclaim_records(records: list[dict], visible: list[dict]) -> list[dict]:
    """Keep fresh rebuilding leaders visible without changing source/scanner rows."""
    output: list[dict] = []
    present: set[str] = set()

    # Preserve all records already admitted by GS373/GS375, but tag eligible copies
    # so every later presentation surface sees the same reconstruction state.
    for record in visible or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present:
            continue
        if reclaim_watch_eligible(record):
            output.append(
                _tag_reclaim_copy(
                    record,
                    awareness_only=bool(record.get(AWARENESS_ONLY_KEY)),
                )
            )
        else:
            output.append(record)
        present.add(symbol)

    # Targeted GS373 exception: only a current >=20% DAY_GAINER with fresh source
    # data, prior continuity, improving VWAP structure, and fresh ST recovery may
    # re-enter the operator surface from as far as 5% below VWAP.  It is always an
    # awareness-only copy and therefore cannot acquire entry/alert authority.
    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present or not reclaim_watch_eligible(record):
            continue
        output.append(_tag_reclaim_copy(record, awareness_only=True))
        present.add(symbol)
    return output


def reclaim_opportunity_state(
    record: dict,
    state_function: Callable[[dict], dict] | None = None,
) -> dict:
    """Insert RECLAIM WATCH below LOOK NOW and above ordinary DEVELOPING."""
    from . import gs310_unified_opportunity_state as unified

    original = state_function or getattr(
        unified.opportunity_state, "_gs376_original", unified.opportunity_state
    )
    view = deepcopy(original(record))
    evaluation = reclaim_watch_evaluation(record)
    if not evaluation["eligible"]:
        return view

    # Stronger established states stay stronger.  Fresh news/re-ignition/volume
    # regime attention remains LOOK NOW; WATCH FOR ENTRY and HALTED are untouched.
    state = view.get("state")
    provenance = set(evaluation["attention_provenance"])
    stronger_attention = bool(
        provenance.intersection(
            {"FRESH_NEWS_SEED", "FRESH_REIGNITION", "FRESH_VOLUME_REGIME"}
        )
    )
    if state in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return view
    if state == unified.LOOK_NOW and stronger_attention:
        return view

    view["state"] = RECLAIM_WATCH
    view["color"] = unified.STATE_COLORS[unified.DEVELOPING]
    view["reason"] = (
        "A current market leader is rebuilding after a reset: SuperTrend has "
        "recovered while VWAP structure is improving."
    )
    view["next_step"] = (
        "Keep the chart open for VWAP reclaim/hold and renewed participation. "
        "Entry remains locked until Walter's scanner and trigger rules align."
    )
    view["reclaim_watch"] = evaluation
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install the presentation-only reconstruction layer after GS375."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs363_operator_attention_hierarchy as hierarchy
    from . import ui

    current_records = ui.actionable_candidate_records
    if not getattr(current_records, "_gs376_reclaim_watch", False):
        original_records = current_records

        def operator_records(records: list[dict]) -> list[dict]:
            return augment_reclaim_records(records, original_records(records))

        _inherit(operator_records, original_records)
        operator_records._gs376_reclaim_watch = True
        operator_records._gs376_original = original_records
        ui.actionable_candidate_records = operator_records

    current_state = unified.opportunity_state
    if not getattr(current_state, "_gs376_reclaim_watch", False):
        original_state = current_state

        def reclaim_state(record: dict) -> dict:
            return reclaim_opportunity_state(record, original_state)

        _inherit(reclaim_state, original_state)
        reclaim_state._gs376_reclaim_watch = True
        reclaim_state._gs376_original = original_state
        unified.opportunity_state = reclaim_state

        for module_name in (
            "gs311_unified_voice",
            "gs314_state_consistency",
            "gs363_operator_attention_hierarchy",
        ):
            try:
                module = __import__(f"mide.{module_name}", fromlist=[module_name])
                if getattr(module, "opportunity_state", None) is original_state:
                    module.opportunity_state = reclaim_state
            except Exception:
                continue

    # Use integer spacing so GS363's diagnostic int() conversion remains truthful.
    hierarchy.STATE_PRIORITY.update(
        {
            unified.WATCH_FOR_ENTRY: 50,
            unified.LOOK_NOW: 40,
            RECLAIM_WATCH: 35,
            unified.DEVELOPING: 30,
            unified.CHASE_WAIT: 20,
            unified.HALTED: 10,
        }
    )
