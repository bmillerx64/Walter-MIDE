"""Authoritative Walter Next Presentation + Audio boundary.

Presentation consumes authoritative evidence/state and renders or announces it. Legacy
UI functions are resolved dynamically so importing this authority during startup can
never freeze an older wrapper implementation.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable
from copy import deepcopy
from functools import wraps
from time import monotonic
from typing import Any


def _ui_call(name: str, *args, **kwargs):
    from mide import ui
    return getattr(ui, name)(*args, **kwargs)


def actionable_candidate_records(*args, **kwargs):
    return _ui_call("actionable_candidate_records", *args, **kwargs)


def data_integrity_markup(*args, **kwargs):
    return _ui_call("data_integrity_markup", *args, **kwargs)


def decision_funnel_markup(*args, **kwargs):
    return _ui_call("decision_funnel_markup", *args, **kwargs)


def inject_css(*args, **kwargs):
    return _ui_call("inject_css", *args, **kwargs)


def market_session_quality_markup(*args, **kwargs):
    return _ui_call("market_session_quality_markup", *args, **kwargs)


def mission_control_header_markup(*args, **kwargs):
    return _ui_call("mission_control_header_markup", *args, **kwargs)


def opportunity_card(*args, **kwargs):
    return _ui_call("opportunity_card", *args, **kwargs)


def play_alert(*args, **kwargs):
    return _ui_call("play_alert", *args, **kwargs)


def radar_table(*args, **kwargs):
    return _ui_call("radar_table", *args, **kwargs)


def rejected_candidates_table(*args, **kwargs):
    return _ui_call("rejected_candidates_table", *args, **kwargs)


def rejection_diagnostics(*args, **kwargs):
    return _ui_call("rejection_diagnostics", *args, **kwargs)


def render_calibration_dashboard(*args, **kwargs):
    return _ui_call("render_calibration_dashboard", *args, **kwargs)


def render_early_setups(*args, **kwargs):
    return _ui_call("render_early_setups", *args, **kwargs)


def render_escalation_engine(*args, **kwargs):
    return _ui_call("render_escalation_engine", *args, **kwargs)


def render_live_opportunity_feed(*args, **kwargs):
    return _ui_call("render_live_opportunity_feed", *args, **kwargs)


def render_walter_mission_control(*args, **kwargs):
    return _ui_call("render_walter_mission_control", *args, **kwargs)


def scanner_v2_dashboard_counts(*args, **kwargs):
    return _ui_call("scanner_v2_dashboard_counts", *args, **kwargs)


def scanner_v2_display_sections(*args, **kwargs):
    return _ui_call("scanner_v2_display_sections", *args, **kwargs)


def render_sidebar_audio_health(*args, **kwargs):
    from mide.gs516_visible_alert_audio_health import render_sidebar_audio_health as current
    return current(*args, **kwargs)


def render_live_evidence_diagnostics(*args, **kwargs):
    from mide.live_evidence_observation import render_live_evidence_diagnostics as current
    return current(*args, **kwargs)


# ---------------------------------------------------------------------------
# GS457 maturation-leader presentation semantics
# ---------------------------------------------------------------------------
#
# Presentation + Audio owns how already-authoritative GS455 progression/state facts
# become a presentation band. This changes no opportunity state, qualification, entry,
# evidence, or execution truth.

MATURATION_WATCH_FOR_ENTRY_BAND = 50
MATURATION_FRESH_BAND = 45
MATURATION_LOOK_NOW_BAND = 40
MATURATION_RECENT_CONFIRMATION_BAND = 35
MATURATION_DEVELOPING_BAND = 30
MATURATION_CHASE_WAIT_BAND = 20
MATURATION_HALTED_BAND = 10
MATURATION_HIGHER_CONFIRMATION_RUNGS = (
    "3m",
    "5m",
    "10m",
    "15m",
)


def maturation_attention(record: dict) -> dict:
    """Return GS457's presentation-only maturation priority details."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs455_early_ignition_3m_confirmation as gs455

    view = unified.opportunity_state(record)
    state = str(view.get("state") or "")
    progression = gs455.crossover_progression(record)
    signal = gs455.progression_signal(record)

    events = progression.get("events") or {}
    active = list(
        progression.get("active_rungs")
        or []
    )
    recent_higher: list[str] = []
    for label in MATURATION_HIGHER_CONFIRMATION_RUNGS:
        if label not in active:
            continue
        event = dict(
            events.get(label)
            or {}
        )
        if (
            event.get("recent")
            and event.get("current_confirmed")
            and event.get("crossed")
        ):
            recent_higher.append(label)

    supporting_flow = bool(
        gs455._supporting_flow(record)
    )
    sustained_confirmation = bool(
        progression.get("ordered")
        and recent_higher
        and supporting_flow
        and state != unified.HALTED
    )
    fresh_maturation = bool(
        signal.get("active")
        and state != unified.HALTED
        and state != unified.WATCH_FOR_ENTRY
    )

    if state == unified.WATCH_FOR_ENTRY:
        band = MATURATION_WATCH_FOR_ENTRY_BAND
        reason = "watch_for_entry"
    elif fresh_maturation:
        band = MATURATION_FRESH_BAND
        reason = "fresh_maturation"
    elif state == unified.LOOK_NOW:
        band = MATURATION_LOOK_NOW_BAND
        reason = "look_now"
    elif sustained_confirmation:
        band = MATURATION_RECENT_CONFIRMATION_BAND
        reason = "recent_3m_plus_confirmation"
    elif state == unified.DEVELOPING:
        band = MATURATION_DEVELOPING_BAND
        reason = "developing"
    elif state == unified.CHASE_WAIT:
        band = MATURATION_CHASE_WAIT_BAND
        reason = "chase_wait"
    else:
        band = MATURATION_HALTED_BAND
        reason = "halted_or_other"

    highest_recent = (
        recent_higher[-1]
        if recent_higher
        else None
    )
    latest_new = progression.get(
        "latest_new_rung"
    )
    priority_rung = (
        latest_new
        or highest_recent
    )
    rung_rank = (
        gs455.CROSSOVER_LADDER.index(
            priority_rung
        )
        + 1
        if priority_rung
        in gs455.CROSSOVER_LADDER
        else 0
    )

    event = (
        dict(
            events.get(priority_rung)
            or {}
        )
        if priority_rung
        else {}
    )
    try:
        age = float(
            event.get("age_seconds")
        )
    except (TypeError, ValueError):
        age = None
    freshness = (
        -age
        if age is not None
        else float("-inf")
    )

    return {
        "band": band,
        "reason": reason,
        "state": state,
        "fresh_maturation": fresh_maturation,
        "sustained_confirmation": sustained_confirmation,
        "recent_higher_rungs": recent_higher,
        "priority_rung": priority_rung,
        "rung_rank": rung_rank,
        "freshness": freshness,
        "progression_stage": progression.get(
            "stage"
        ),
        "progression_sequence": (
            progression.get("sequence")
            or ""
        ),
        "supporting_flow": supporting_flow,
    }


def _maturation_attention_compat(record: dict) -> dict:
    """Honor historical GS457 monkeypatch/warm-runtime seams without recursion."""
    from mide import gs457_maturation_leader_priority as gs457

    current = getattr(
        gs457,
        "maturation_attention",
        None,
    )
    if (
        callable(current)
        and not getattr(
            current,
            "_walter_next_presentation_facade",
            False,
        )
    ):
        return current(record)
    return maturation_attention(record)


# GS457 maturation ordering and historical GS369 bind.

MATURATION_ORDER_OWNER = "_walter_gs457_maturation_leader_priority_owner"


def effective_maturation_priority(
    attention: dict,
) -> tuple[int, float]:
    """Use crossover tie-breaks only for GS457's promoted maturation bands."""
    promoted = bool(
        attention.get("fresh_maturation")
        or attention.get("sustained_confirmation")
    )
    if not promoted:
        return 0, float("-inf")
    return (
        int(attention.get("rung_rank") or 0),
        float(
            attention.get(
                "freshness",
                float("-inf"),
            )
        ),
    )


def maturation_priority_sort_key(
    record: dict,
) -> tuple:
    """Return GS457's presentation keys with established ordinary tie-breaks."""
    from mide import ui
    from mide.gs363_operator_attention_hierarchy import (
        operator_attention_score,
    )

    attention = _maturation_attention_compat(
        record
    )
    rung_rank, freshness = (
        effective_maturation_priority(
            attention
        )
    )
    try:
        established = (
            ui.trader_priority_sort_key(
                record
            )
        )
    except Exception:
        established = ()
    return (
        int(attention["band"]),
        rung_rank,
        freshness,
        int(
            operator_attention_score(
                record
            )
        ),
        established,
    )


def ordered_maturation_records(
    records: list[dict],
) -> list[dict]:
    """Preserve GS457's stable presentation-only maturation ordering."""
    from mide import ui
    from mide.gs363_operator_attention_hierarchy import (
        operator_attention_score,
    )

    pairs = [
        (
            record,
            _maturation_attention_compat(
                record
            ),
        )
        for record in (
            records
            or []
        )
    ]
    pairs.sort(
        key=lambda item: str(
            item[0].get("symbol")
            or ""
        ).upper()
    )
    try:
        pairs.sort(
            key=lambda item: (
                ui.trader_priority_sort_key(
                    item[0]
                )
            ),
            reverse=True,
        )
    except Exception:
        pass
    pairs.sort(
        key=lambda item: (
            operator_attention_score(
                item[0]
            )
        ),
        reverse=True,
    )
    pairs.sort(
        key=lambda item: (
            effective_maturation_priority(
                item[1]
            )[1]
        ),
        reverse=True,
    )
    pairs.sort(
        key=lambda item: (
            effective_maturation_priority(
                item[1]
            )[0]
        ),
        reverse=True,
    )
    pairs.sort(
        key=lambda item: int(
            item[1]["band"]
        ),
        reverse=True,
    )
    return [
        record
        for record, _attention
        in pairs
    ]


def install_maturation_leader_priority() -> None:
    """Bind GS457 at its historical final GS369 ordering seam."""
    from mide import gs369_escalation_priority_order as gs369

    current = (
        gs369.ordered_escalation_records
    )
    if getattr(
        current,
        MATURATION_ORDER_OWNER,
        False,
    ):
        return

    def ordered_escalation_records(
        records: list[dict],
    ) -> list[dict]:
        return ordered_maturation_records(
            records
        )

    for name, value in getattr(
        current,
        "__dict__",
        {},
    ).items():
        if (
            name.startswith("_gs")
            and not hasattr(
                ordered_escalation_records,
                name,
            )
        ):
            setattr(
                ordered_escalation_records,
                name,
                value,
            )

    ordered_escalation_records._gs457_maturation_leader_priority = True
    ordered_escalation_records._gs457_original = current
    setattr(
        ordered_escalation_records,
        MATURATION_ORDER_OWNER,
        True,
    )
    gs369.ordered_escalation_records = (
        ordered_escalation_records
    )


# ---------------------------------------------------------------------------
# Authoritative operator ordering
# ---------------------------------------------------------------------------
#
# Historically the final card order accumulated as nested GS463 -> GS465 ->
# GS497 -> GS517 -> GS539 wrappers. Walter Next keeps the same staged semantics
# but owns them in one Presentation + Audio wrapper. Each historical installer
# activates its stage at the same point in startup; no additional wrapper is added.

_OPERATOR_ORDER_OWNER = "_walter_next_authoritative_operator_order_owner"

STATE_FIRST_WATCH_FOR_ENTRY_BAND = 60
STATE_FIRST_LOOK_NOW_BAND = 50
STATE_FIRST_JET_FUEL_BAND = 47
STATE_FIRST_EARLY_WATCH_BAND = 46
STATE_FIRST_FRESH_MATURATION_BAND = 45
STATE_FIRST_TRAJECTORY_BAND = 44
STATE_FIRST_RECENT_CONFIRMATION_BAND = 43
STATE_FIRST_DEVELOPING_BAND = 30
STATE_FIRST_CHASE_WAIT_BAND = 20
STATE_FIRST_OTHER_BAND = 10

CONTIGUOUS_WATCH_FOR_ENTRY_BAND = 60
CONTIGUOUS_LOOK_NOW_BAND = 50
CONTIGUOUS_DEVELOPING_BAND = 40
CONTIGUOUS_CHASE_WAIT_BAND = 30
CONTIGUOUS_HALTED_BAND = 20
CONTIGUOUS_OTHER_BAND = 10

_OPERATOR_ORDER_STAGE_SEQUENCE = (
    "state_first",
    "state_contiguous",
    "rank_aware",
    "fresh_event",
    "pe_strength",
)

_OPERATOR_ORDER_STAGE_METADATA = {
    "state_first": (
        "_gs463_state_first_operator_order",
        "_gs463_original",
    ),
    "state_contiguous": (
        "_gs465_presentation_priority_cleanup",
        "_gs465_original",
    ),
    "rank_aware": (
        "_gs497_rank_aware_attention_order",
        "_gs497_original",
    ),
    "fresh_event": (
        "_gs517_fresh_event_priority",
        "_gs517_original",
    ),
    "pe_strength": (
        "_gs539_pe_strength_order",
        "_gs539_original",
    ),
}


def effective_operator_attention_band(record: dict) -> int:
    """Return the historical GS463 state/attention presentation band."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    state = str(unified.opportunity_state(record).get("state") or "")
    if state == unified.WATCH_FOR_ENTRY:
        return STATE_FIRST_WATCH_FOR_ENTRY_BAND
    if state == unified.LOOK_NOW:
        return STATE_FIRST_LOOK_NOW_BAND

    preflip = gs462.preflip_ignition_watch(record)
    if preflip.get("active"):
        return (
            STATE_FIRST_JET_FUEL_BAND
            if preflip.get("jet_fuel")
            else STATE_FIRST_EARLY_WATCH_BAND
        )

    maturation = _maturation_attention_compat(record)
    if maturation.get("fresh_maturation"):
        return STATE_FIRST_FRESH_MATURATION_BAND

    if gs459.trajectory_attention(record).get("active"):
        return STATE_FIRST_TRAJECTORY_BAND

    if maturation.get("sustained_confirmation"):
        return STATE_FIRST_RECENT_CONFIRMATION_BAND

    if state == unified.DEVELOPING:
        return STATE_FIRST_DEVELOPING_BAND
    if state == unified.CHASE_WAIT:
        return STATE_FIRST_CHASE_WAIT_BAND
    return STATE_FIRST_OTHER_BAND


def _state_first_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(key=effective_operator_attention_band, reverse=True)
    return output


def ordered_state_first_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    rows = list(baseline_order(records) if baseline_order is not None else (records or []))
    return _state_first_stage(rows)


def strict_state_band(record: dict) -> int:
    """Return the historical GS465 non-negotiable visible state band."""
    from mide import gs310_unified_opportunity_state as unified

    state = str(unified.opportunity_state(record).get("state") or "")
    if state == unified.WATCH_FOR_ENTRY:
        return CONTIGUOUS_WATCH_FOR_ENTRY_BAND
    if state == unified.LOOK_NOW:
        return CONTIGUOUS_LOOK_NOW_BAND
    if state == unified.DEVELOPING:
        return CONTIGUOUS_DEVELOPING_BAND
    if state == unified.CHASE_WAIT:
        return CONTIGUOUS_CHASE_WAIT_BAND
    if state == unified.HALTED:
        return CONTIGUOUS_HALTED_BAND
    return CONTIGUOUS_OTHER_BAND


def attention_tiebreak(record: dict) -> tuple[int, float, float]:
    """Rank attention evidence only inside an already-equal Opportunity State."""
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    preflip = gs462.preflip_ignition_watch(record)
    if preflip.get("active"):
        one_gap = (preflip.get("one_minute") or {}).get("st_gap_pct")
        three_gap = (preflip.get("three_minute") or {}).get("st_gap_pct")
        try:
            one_gap = float(one_gap)
        except (TypeError, ValueError):
            one_gap = 999.0
        try:
            three_gap = float(three_gap)
        except (TypeError, ValueError):
            three_gap = 999.0
        return (60 if preflip.get("jet_fuel") else 55, -one_gap, -three_gap)

    maturation = _maturation_attention_compat(record)
    if maturation.get("fresh_maturation"):
        return (50, 0.0, 0.0)
    if gs459.trajectory_attention(record).get("active"):
        return (45, 0.0, 0.0)
    if maturation.get("sustained_confirmation"):
        return (40, 0.0, 0.0)
    return (0, 0.0, 0.0)


def _state_contiguous_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(key=attention_tiebreak, reverse=True)
    output.sort(key=strict_state_band, reverse=True)
    return output


def ordered_state_contiguous_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    rows = list(baseline_order(records) if baseline_order is not None else (records or []))
    return _state_contiguous_stage(rows)


def current_mission_rank(record: dict) -> int | None:
    """Return a current positive Mission Ranking, rejecting stale terminal residue."""
    value = record.get("mission_rank")
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return None
    if rank <= 0:
        return None

    terminal_stage = str(record.get("terminal_stage") or "").strip()
    terminal_outcome = str(record.get("terminal_outcome") or "").strip().lower()
    if terminal_stage and terminal_stage != "Mission Ranking and Publication":
        return None
    if terminal_outcome and "ranked" not in terminal_outcome:
        return None
    return rank


def _rank_aware_stage(rows: list[dict]) -> list[dict]:
    from mide import gs310_unified_opportunity_state as unified

    ready: list[dict] = []
    ranked: list[dict] = []
    unranked: list[dict] = []
    halted: list[dict] = []

    for record in rows:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            ready.append(record)
        elif state == unified.HALTED:
            halted.append(record)
        elif current_mission_rank(record) is not None:
            ranked.append(record)
        else:
            unranked.append(record)

    ranked.sort(key=lambda record: current_mission_rank(record) or 10**9)
    return ready + ranked + unranked + halted


def ordered_rank_aware_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _rank_aware_stage(rows)


def fresh_maturation_event(record: dict) -> bool:
    """Return current GS455 maturation-event truth without inventing thresholds."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs455_early_ignition_3m_confirmation as gs455

    try:
        state = str(unified.opportunity_state(record).get("state") or "")
    except Exception:
        state = ""
    if state in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return False
    try:
        return bool(gs455.progression_signal(record).get("active"))
    except Exception:
        return False


def _fresh_event_stage(rows: list[dict]) -> list[dict]:
    from mide import gs310_unified_opportunity_state as unified

    def attention_band(record: dict) -> int:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            return 3
        if state == unified.HALTED:
            return 0
        if fresh_maturation_event(record):
            return 2
        return 1

    output = list(rows)
    output.sort(key=attention_band, reverse=True)
    return output


def ordered_fresh_event_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _fresh_event_stage(rows)


# ---------------------------------------------------------------------------
# GS527 explosive 30s operator-attention watch
# ---------------------------------------------------------------------------
#
# GS527 is presentation-only. It consumes already-computed 30s/VWAP/flow evidence,
# annotates the visible state without promotion, lifts a fresh burst in operator
# ordering, and supplies an attention-only spoken cue when stronger audio is absent.
#
# The historical gs527 module remains the mutable compatibility seam. These authority
# functions deliberately call back through that facade where the original module used
# module globals, preserving monkeypatches and retained warm-runtime wrapper behavior.

_EXPLOSIVE_30S_STATE_OWNER = "_walter_gs527_explosive_30s_surge_state_owner"
_EXPLOSIVE_30S_ORDER_OWNER = "_walter_gs527_explosive_30s_surge_order_owner"
_EXPLOSIVE_30S_AUDIO_OWNER = "_walter_gs527_explosive_30s_surge_audio_owner"


def explosive_30s_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def explosive_30s_surge(record: dict) -> dict:
    """Return bounded attention truth from already-computed 30s tripwire evidence."""
    from mide import gs462_preflip_ignition_watch as gs462
    from mide import gs527_explosive_30s_surge_watch as gs527

    thirty = gs462._timeframe_detail(record, "30s")
    age = gs527._number(thirty.get("flip_age_seconds"))
    volume = gs527._number(record.get("volume_acceleration_30s"))
    dollar = gs527._number(record.get("dollar_flow_acceleration_30s"))

    active = bool(
        thirty.get("bullish")
        and thirty.get("above_vwap")
        and age is not None
        and 0.0 <= age <= float(gs527.FRESH_BURST_SECONDS)
        and volume is not None
        and volume >= float(gs527.MIN_VOLUME_ACCELERATION_30S)
        and dollar is not None
        and dollar >= float(gs527.MIN_DOLLAR_FLOW_ACCELERATION_30S)
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
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs527_explosive_30s_surge_watch as gs527

    view = original(record)
    event = gs527.explosive_30s_surge(record)
    if not event.get("active") or view.get("state") == unified.HALTED:
        return view

    result = deepcopy(view)
    provenance = list(result.get("attention_provenance") or [])
    if gs527._PROVENANCE not in provenance:
        provenance.append(gs527._PROVENANCE)
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


def explosive_30s_attention_band(record: dict) -> int:
    """Final event ordering: entry > fresh maturation > explosive 30s > baseline."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs517_fresh_event_priority as gs517
    from mide import gs527_explosive_30s_surge_watch as gs527

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
    if gs527.explosive_30s_surge(record).get("active"):
        return 2
    return 1


def ordered_explosive_30s_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    """Stable event lift over the established GS517/Mission-Rank order."""
    from mide import gs527_explosive_30s_surge_watch as gs527

    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    rows.sort(key=gs527._attention_band, reverse=True)
    return rows


def explosive_30s_audio_phrase(records: list[dict]) -> str:
    """Speak one attention-only surge cue without manufacturing LOOK NOW/ENTRY READY."""
    from mide import gs527_explosive_30s_surge_watch as gs527

    for record in records or []:
        event = gs527.explosive_30s_surge(record)
        if not event.get("active") or not event.get("symbol"):
            continue
        return (
            f"{event['symbol']}. EARLY SURGE WATCH. Fresh 30 second bullish flip with "
            f"{event['volume_acceleration_30s']:.1f} times volume and "
            f"{event['dollar_flow_acceleration_30s']:.1f} times dollar flow. "
            "One minute confirmation is still pending. Attention only."
        )
    return ""


def install_explosive_30s_state() -> None:
    """Bind GS527 explanatory state annotation at its historical install position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy
    from mide import gs527_explosive_30s_surge_watch as gs527

    current = unified.opportunity_state
    if getattr(current, _EXPLOSIVE_30S_STATE_OWNER, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return gs527.state_with_explosive_30s(current, record)

        _inherit_audio_wrapper(calibrated, current)
        calibrated._gs527_explosive_30s_surge_watch = True
        calibrated._gs527_original = current
        setattr(calibrated, _EXPLOSIVE_30S_STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def install_explosive_30s_order() -> None:
    """Bind the historical GS527 event-lift wrapper without changing its position."""
    from mide import gs369_escalation_priority_order as gs369
    from mide import gs527_explosive_30s_surge_watch as gs527

    current = gs369.ordered_escalation_records
    if getattr(current, _EXPLOSIVE_30S_ORDER_OWNER, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return gs527.ordered_explosive_30s_records(
            records,
            baseline_order=current,
        )

    _inherit_audio_wrapper(ordered_escalation_records, current)
    ordered_escalation_records._gs527_explosive_30s_surge_watch = True
    ordered_escalation_records._gs527_original = current
    setattr(
        ordered_escalation_records,
        _EXPLOSIVE_30S_ORDER_OWNER,
        True,
    )
    gs369.ordered_escalation_records = ordered_escalation_records


def install_explosive_30s_audio() -> None:
    """Bind GS527 attention-only audio after established higher-tier audio."""
    from mide import escalation
    from mide.gs365_chime_semantic_classifier import semantic_chime_count
    from mide import gs527_explosive_30s_surge_watch as gs527

    current = escalation.escalation_alert_phrase
    if getattr(current, _EXPLOSIVE_30S_AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        established = current(rows)
        if established and semantic_chime_count(established) >= 2:
            return established
        burst = gs527.explosive_30s_audio_phrase(rows)
        return burst or established

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs527_explosive_30s_surge_watch = True
    alert_phrase._gs527_original = current
    setattr(alert_phrase, _EXPLOSIVE_30S_AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


def install_explosive_30s_presentation() -> None:
    """Install GS527's state, ordering, and audio slices at the historical boundary."""
    install_explosive_30s_state()
    install_explosive_30s_order()
    install_explosive_30s_audio()


def _pe_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def participation_value(record: dict) -> float | None:
    for key in ("participation_surge_score", "participation_score"):
        value = _pe_number(record.get(key))
        if value is not None:
            return value
    return None


def expansion_value(record: dict) -> float | None:
    for key in ("expansion_quality", "expansion_score"):
        value = _pe_number(record.get(key))
        if value is not None:
            return value
    return None


def pe_strength_score(record: dict) -> float | None:
    participation = participation_value(record)
    expansion = expansion_value(record)
    if participation is None or expansion is None:
        return None
    return (participation + expansion) / 2.0


def _pe_halted(record: dict) -> bool:
    if any(
        record.get(key) is True
        for key in ("halted", "is_halted", "suspended", "is_suspended")
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).casefold()
    return "halt" in text or "suspend" in text


def _pe_strength_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(
        key=lambda record: (
            pe_strength_score(record)
            if pe_strength_score(record) is not None
            else float("-inf")
        ),
        reverse=True,
    )
    output.sort(
        key=lambda record: bool(record.get("qualified_for_entry") is True),
        reverse=True,
    )
    output.sort(key=_pe_halted)
    return output


def ordered_pe_strength_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _pe_strength_stage(rows)


def _apply_operator_order_stages(
    rows: list[dict],
    active_stages: set[str],
) -> list[dict]:
    output = list(rows)
    for stage in _OPERATOR_ORDER_STAGE_SEQUENCE:
        if stage not in active_stages:
            continue
        if stage == "state_first":
            output = _state_first_stage(output)
        elif stage == "state_contiguous":
            output = _state_contiguous_stage(output)
        elif stage == "rank_aware":
            output = _rank_aware_stage(output)
        elif stage == "fresh_event":
            output = _fresh_event_stage(output)
        elif stage == "pe_strength":
            output = _pe_strength_stage(output)
    return output


def activate_operator_order_stage(stage: str) -> None:
    """Activate one historical ordering stage inside one authoritative wrapper."""
    if stage not in _OPERATOR_ORDER_STAGE_SEQUENCE:
        raise ValueError(f"unknown operator-order stage: {stage}")

    from mide import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OPERATOR_ORDER_OWNER, False):
        wrapper = current
    else:
        baseline = current

        def ordered_escalation_records(records: list[dict]) -> list[dict]:
            rows = list(baseline(records))
            active = set(
                getattr(
                    ordered_escalation_records,
                    "_walter_next_operator_order_stages",
                    set(),
                )
            )
            return _apply_operator_order_stages(rows, active)

        _inherit_audio_wrapper(ordered_escalation_records, baseline)
        setattr(ordered_escalation_records, _OPERATOR_ORDER_OWNER, True)
        ordered_escalation_records._walter_next_operator_order_stages = set()
        ordered_escalation_records._walter_next_operator_order_baseline = baseline
        gs369.ordered_escalation_records = ordered_escalation_records
        wrapper = ordered_escalation_records

    active = set(getattr(wrapper, "_walter_next_operator_order_stages", set()))
    active.add(stage)
    wrapper._walter_next_operator_order_stages = active

    marker, original_attr = _OPERATOR_ORDER_STAGE_METADATA[stage]
    setattr(wrapper, marker, True)
    if not hasattr(wrapper, original_attr):
        setattr(
            wrapper,
            original_attr,
            getattr(wrapper, "_walter_next_operator_order_baseline", None),
        )


_PE_STRENGTH_STATE_OWNER = "_walter_gs539_pe_strength_state_owner"


def state_with_pe_strength(original, record: dict) -> dict:
    """Explain visible P/E Strength without changing Opportunity State/color."""
    view = original(record)
    score = pe_strength_score(record)
    if score is None:
        return view
    result = deepcopy(view)
    result["pe_strength_score"] = round(score, 1)
    reason = str(result.get("reason") or "").strip()
    prefix = f"P/E Strength {score:.0f}/100"
    if not reason.startswith("P/E Strength "):
        result["reason"] = f"{prefix} · {reason}".strip(" ·")
    return result


def install_pe_strength_state() -> None:
    """Bind the historical GS539 explanatory state wrapper."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current_state = unified.opportunity_state
    if getattr(current_state, _PE_STRENGTH_STATE_OWNER, False):
        calibrated = current_state
    else:
        @wraps(current_state)
        def calibrated(record: dict) -> dict:
            return state_with_pe_strength(current_state, record)

        _inherit_audio_wrapper(calibrated, current_state)
        calibrated._gs539_pe_strength_order = True
        calibrated._gs539_original = current_state
        setattr(calibrated, _PE_STRENGTH_STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def install_pe_strength_order() -> None:
    install_pe_strength_state()
    activate_operator_order_stage("pe_strength")


# ---------------------------------------------------------------------------
# Base extraordinary-mover presentation
# ---------------------------------------------------------------------------
#
# GS333's original detector/selector/render responsibilities belong entirely to
# Presentation + Audio. The public gs333 module remains a compatibility facade so
# later historical installers can still replace its callables in the validated order.

EXTREME_MOVER_PCT = 75.0


def _extreme_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _extreme_headline(record: dict) -> str:
    for key in ("headline", "catalyst_headline", "news_headline", "latest_headline"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    evidence = record.get("news_evidence") or record.get("catalyst_evidence") or {}
    if isinstance(evidence, dict):
        for key in ("headline", "title"):
            value = str(evidence.get(key) or "").strip()
            if value:
                return value
    return ""


def _extreme_attention(record: dict) -> tuple[str, ...]:
    try:
        from mide.gs309_current_attention_mission import current_attention_provenance

        return tuple(current_attention_provenance(record))
    except Exception:
        return ()


def _extreme_halted(record: dict) -> bool:
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


def base_extreme_market_event(record: dict) -> dict | None:
    """Describe an extraordinary attention event without granting trade authority."""
    pct_change = _extreme_number(record, "pct_change", default=0.0) or 0.0
    provenance = _extreme_attention(record)
    current = bool({"WEBULL_TOP_MOVER", "FRESH_NEWS_SEED"}.intersection(provenance))
    if pct_change < EXTREME_MOVER_PCT or not current:
        return None

    distance = _extreme_number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").lower()
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    halted = _extreme_halted(record)
    headline = _extreme_headline(record)

    if halted:
        label = "HALTED · WATCH RESUME"
        guidance = (
            "Do not anticipate the reopen. Reassess fresh price, VWAP, trend, and "
            "volume after trading resumes."
        )
    elif distance is not None and distance > 5.0:
        label = "EXTREME MOVER · DO NOT CHASE"
        guidance = (
            "Major market event, not an entry signal. Wait for a constructive reset "
            "or halt/resume setup before reconsidering."
        )
    else:
        label = "EXTREME MOVER · LOOK NOW"
        guidance = (
            "Open the chart now, but require the normal entry evidence before "
            "considering a trade."
        )

    return {
        "symbol": str(record.get("symbol") or "").upper(),
        "pct_change": round(pct_change, 1),
        "vwap_distance_pct": None if distance is None else round(distance, 1),
        "vwap_relation": relation,
        "trend": trend,
        "halted": halted,
        "headline": headline,
        "provenance": provenance,
        "label": label,
        "guidance": guidance,
    }


def prioritized_extreme_event(
    records: Iterable[dict],
) -> tuple[dict | None, dict | None]:
    """Select the current extreme using the latest installed event semantics."""
    # Deliberately resolve through the compatibility module at call time. GS393,
    # GS465, and GS495 historically refine these public callables later in startup.
    from mide import gs333_extreme_mover_operator_priority as gs333

    choices: list[tuple[tuple, dict, dict]] = []
    for record in records or []:
        event = gs333.extreme_market_event(record)
        if not event:
            continue
        dollar_volume = _extreme_number(record, "dollar_volume", default=0.0) or 0.0
        choices.append(
            (
                (1 if event["halted"] else 0, event["pct_change"], dollar_volume),
                record,
                event,
            )
        )
    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def extreme_event_markup(event: dict) -> str:
    distance = event.get("vwap_distance_pct")
    vwap = (
        "VWAP distance unavailable"
        if distance is None
        else f"{abs(float(distance)):.1f}% {'above' if float(distance) >= 0 else 'below'} VWAP"
    )
    trend = (
        "SuperTrend bullish"
        if event.get("trend")
        else "SuperTrend not confirmed"
    )
    headline = str(event.get("headline") or "").strip()
    catalyst = (
        f"<div class='small' style='margin-top:8px'><b>Catalyst:</b> "
        f"{html.escape(headline)}</div>"
        if headline
        else ""
    )
    return (
        "<div class='recommendation-box' style='--recommendation-color:#facc15'>"
        f"<div class='recommendation-label'>{html.escape(event['symbol'])} · "
        f"{html.escape(event['label'])}</div>"
        f"<div class='recommendation-message'>Current move: "
        f"+{float(event['pct_change']):.1f}% · {html.escape(vwap)} · "
        f"{html.escape(trend)}</div>"
        f"{catalyst}"
        f"<div class='small' style='margin-top:8px'><b>Walter:</b> "
        f"{html.escape(event['guidance'])}</div>"
        "</div>"
    )


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def install_base_extreme_presentation() -> None:
    """Bind GS333's historical action-first and maintenance-sidebar presentation."""
    from mide import ui

    if getattr(ui.render_walter_mission_control, "_gs333_operator_priority", False):
        return

    current_action = ui.render_walter_mission_control

    def render_action_first(records: list[dict]) -> None:
        if not _in_streamlit_run():
            return current_action(records)
        extreme_record, event = prioritized_extreme_event(records)
        if event is not None and extreme_record is not None:
            ui.st.markdown(extreme_event_markup(event), unsafe_allow_html=True)
            remaining = [record for record in records if record is not extreme_record]
            if remaining:
                current_action(remaining)
            return
        current_action(records)

    _inherit_audio_wrapper(render_action_first, current_action)
    render_action_first._gs333_operator_priority = True
    render_action_first._gs333_original = current_action
    ui.render_walter_mission_control = render_action_first

    import streamlit as st

    current_expander = st.expander
    if not getattr(current_expander, "_gs333_diagnostics_sidebar", False):
        diagnostic_labels = {"System Status", "Decision Funnel audit trails"}

        def diagnostic_expander(label, *args, **kwargs):
            if _in_streamlit_run() and str(label) in diagnostic_labels:
                return st.sidebar.expander(str(label), *args, **kwargs)
            return current_expander(label, *args, **kwargs)

        _inherit_audio_wrapper(diagnostic_expander, current_expander)
        diagnostic_expander._gs333_diagnostics_sidebar = True
        diagnostic_expander._gs333_original = current_expander
        st.expander = diagnostic_expander
        ui.st.expander = diagnostic_expander

    current_play_alert = ui.play_alert
    if not getattr(current_play_alert, "_gs333_voice_sidebar", False):
        def play_alert_in_sidebar(*args, **kwargs):
            if _in_streamlit_run():
                with st.sidebar.expander("Voice transport", expanded=False):
                    return current_play_alert(*args, **kwargs)
            return current_play_alert(*args, **kwargs)

        _inherit_audio_wrapper(play_alert_in_sidebar, current_play_alert)
        play_alert_in_sidebar._gs333_voice_sidebar = True
        play_alert_in_sidebar._gs333_original = current_play_alert
        ui.play_alert = play_alert_in_sidebar


EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS = 180.0
_extreme_first_seen: dict[str, float] = {}


def _actionable_operator_symbols(rows: list[dict]) -> set[str]:
    """Return symbols whose current state outranks an extended DO-NOT-CHASE banner."""
    from mide import gs310_unified_opportunity_state as unified

    priority_states = {
        unified.WATCH_FOR_ENTRY,
        unified.LOOK_NOW,
        unified.DEVELOPING,
    }
    symbols: set[str] = set()
    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        try:
            state = unified.opportunity_state(record).get("state")
        except Exception:
            continue
        if state in priority_states:
            symbols.add(symbol)
    return symbols


def prioritized_extreme_with_decay(
    records,
    *,
    now: float | None = None,
) -> tuple[dict | None, dict | None]:
    """Apply GS393/GS439 action-first TTL behavior to current extreme events."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    stamp = monotonic() if now is None else float(now)
    rows = list(records or [])
    actionable_symbols = _actionable_operator_symbols(rows)
    extreme_symbols: set[str] = set()
    choices: list[tuple[tuple, dict, dict]] = []

    for record in rows:
        event = extreme.extreme_market_event(record)
        if not event:
            continue
        symbol = str(event.get("symbol") or "").upper()
        if not symbol:
            continue
        extreme_symbols.add(symbol)
        _extreme_first_seen.setdefault(symbol, stamp)

        label = str(event.get("label") or "").upper()
        elapsed = max(0.0, stamp - _extreme_first_seen[symbol])
        competing_action = any(
            candidate_symbol != symbol for candidate_symbol in actionable_symbols
        )
        eligible = (
            "HALTED" in label
            or "LOOK NOW" in label
            or (
                not competing_action
                and elapsed <= EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
            )
        )
        if not eligible:
            continue

        dollar_volume = _extreme_number(
            record,
            "dollar_volume",
            default=0.0,
        ) or 0.0
        choices.append(
            (
                (
                    1 if event.get("halted") else 0,
                    float(event.get("pct_change") or 0.0),
                    dollar_volume,
                ),
                record,
                event,
            )
        )

    for symbol in list(_extreme_first_seen):
        if symbol not in extreme_symbols:
            _extreme_first_seen.pop(symbol, None)

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def install_extreme_banner_decay() -> None:
    """Bind GS393/GS439 action-first extreme priority at its historical position."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    current = extreme.prioritized_extreme_event
    if getattr(current, "_gs439_action_first_extreme", False):
        return

    def prioritized_with_decay(records, *, now: float | None = None):
        return prioritized_extreme_with_decay(records, now=now)

    prioritized_with_decay._gs393_extreme_decay = True
    prioritized_with_decay._gs439_action_first_extreme = True
    prioritized_with_decay._gs393_original = current
    extreme.prioritized_extreme_event = prioritized_with_decay


def reset_extreme_banner_decay_state() -> None:
    _extreme_first_seen.clear()


# ---------------------------------------------------------------------------
# Native market-event presentation
# ---------------------------------------------------------------------------

_LATEST_ACTIONABLE_SYMBOLS: set[str] = set()
_MARKET_EVENT_MISSION_OWNER = "_walter_gs334_market_event_symbols"
_MARKET_EVENT_HEADER_OWNER = "_walter_gs334_market_event_lane"


def visible_market_events(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None,
) -> list[dict]:
    """Suppress market-awareness rows already represented by current trade records."""
    active = {
        str(symbol or "").strip().upper()
        for symbol in actionable_symbols or []
    }
    return [
        dict(event)
        for event in events or []
        if str(event.get("symbol") or "").strip().upper() not in active
    ]


def market_event_markup(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None = None,
) -> str:
    """Render the established attention-only native market-events strip."""
    visible = visible_market_events(events, actionable_symbols)
    if not visible:
        return ""

    chips = "".join(
        (
            "<span style='display:inline-block;margin:3px 8px 3px 0;padding:5px 9px;"
            "border:1px solid #f59e0b;border-radius:8px;background:#111827;'>"
            f"<b>{html.escape(str(event['symbol']))}</b> "
            f"<span style='color:#fbbf24'>+{float(event['pct_change']):.1f}%</span> "
            f"<span style='color:#94a3b8'>#{int(event['rank'])} Webull</span></span>"
        )
        for event in visible
    )
    return (
        "<div style='margin:10px 0 14px 0;padding:10px 14px;border:1px solid #92400e;"
        "border-left:4px solid #f59e0b;border-radius:10px;background:#0b111b;'>"
        "<div style='font-weight:800;letter-spacing:.06em;color:#fbbf24'>"
        "⚡ LIVE MARKET EVENTS · ATTENTION ONLY</div>"
        f"<div style='margin-top:5px'>{chips}</div>"
        "<div style='margin-top:4px;color:#94a3b8;font-size:.86rem'>"
        "Extraordinary current movers outside Walter's trade-qualified results. "
        "Open the chart if useful; normal entry gates still apply.</div></div>"
    )


def _streamlit_completed_scan_market_events() -> list[dict]:
    try:
        import streamlit as st
        from mide.authorities import market_evidence

        return market_evidence.completed_scan_market_events(st.session_state)
    except Exception:
        return []


def install_market_event_presentation() -> None:
    """Bind GS334's current-symbol tracking and header strip at its historical point."""
    from mide import ui
    from mide.authorities import market_evidence

    current_mission = ui.walter_mission_control
    if not getattr(current_mission, _MARKET_EVENT_MISSION_OWNER, False):
        @wraps(current_mission)
        def mission_with_current_symbols(records: list[dict]) -> dict:
            _LATEST_ACTIONABLE_SYMBOLS.clear()
            _LATEST_ACTIONABLE_SYMBOLS.update(
                str(record.get("symbol") or "").strip().upper()
                for record in records or []
                if str(record.get("symbol") or "").strip()
            )
            return current_mission(records)

        _inherit_audio_wrapper(mission_with_current_symbols, current_mission)
        mission_with_current_symbols._gs334_market_event_symbols = True
        mission_with_current_symbols._gs334_original = current_mission
        setattr(
            mission_with_current_symbols,
            _MARKET_EVENT_MISSION_OWNER,
            True,
        )
        ui.walter_mission_control = mission_with_current_symbols

    current_header = ui.mission_control_header_markup
    if not getattr(current_header, _MARKET_EVENT_HEADER_OWNER, False):
        @wraps(current_header)
        def header_with_market_events(*args, **kwargs):
            markup = current_header(*args, **kwargs)
            if not _in_streamlit_run():
                return markup
            persisted = _streamlit_completed_scan_market_events()
            events = (
                persisted
                if persisted
                else market_evidence._LATEST_MARKET_EVENTS
            )
            return markup + market_event_markup(
                events,
                _LATEST_ACTIONABLE_SYMBOLS,
            )

        _inherit_audio_wrapper(header_with_market_events, current_header)
        header_with_market_events._gs334_market_event_lane = True
        header_with_market_events._gs335_persistent_market_events = True
        header_with_market_events._gs334_original = current_header
        setattr(header_with_market_events, _MARKET_EVENT_HEADER_OWNER, True)
        ui.mission_control_header_markup = header_with_market_events


# ---------------------------------------------------------------------------
# Market-leader continuity presentation
# ---------------------------------------------------------------------------

MAJOR_MOVER_PCT = 20.0
MIN_DOLLAR_VOLUME = 250_000.0
LEADER_DOMINANCE = 78.0
_MARKET_LEADER_CONTINUITY_OWNER = "_walter_gs443_market_leader_radar_continuity"


def _market_leader_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _focused_mission_symbols(mission: dict | None) -> set[str]:
    symbols: set[str] = set()
    if not isinstance(mission, dict):
        return symbols
    for key in ("primary", "secondary"):
        item = mission.get(key)
        if not isinstance(item, dict):
            continue
        record = item.get("record")
        if isinstance(record, dict):
            symbol = str(record.get("symbol") or "").strip().upper()
            if symbol:
                symbols.add(symbol)
    return symbols


def market_leader_candidate(
    records: Iterable[dict],
    *,
    mission: dict | None = None,
) -> tuple[dict | None, dict | None]:
    """Return one uncovered current leader for watch-only continuity."""
    from mide.gs305_second_wave_attention import attention_evaluation
    from mide.gs309_current_attention_mission import current_attention_provenance
    from mide.gs333_extreme_mover_operator_priority import prioritized_extreme_event

    rows = list(records or [])
    focused = _focused_mission_symbols(mission)
    displayed_extreme, _event = prioritized_extreme_event(rows)
    displayed_extreme_symbol = (
        str(displayed_extreme.get("symbol") or "").strip().upper()
        if isinstance(displayed_extreme, dict)
        else ""
    )
    choices: list[tuple[tuple[float, float, float], dict, dict]] = []

    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in focused or symbol == displayed_extreme_symbol:
            continue

        provenance = tuple(current_attention_provenance(record))
        if "WEBULL_TOP_MOVER" not in provenance:
            continue

        pct_change = _market_leader_number(record, "pct_change", default=0.0) or 0.0
        dollar_volume = (
            _market_leader_number(record, "dollar_volume", default=0.0) or 0.0
        )
        dominance = (
            _market_leader_number(
                record,
                "market_dominance_score",
                default=0.0,
            )
            or 0.0
        )
        if pct_change < MAJOR_MOVER_PCT:
            continue
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        if dominance < LEADER_DOMINANCE:
            continue

        existing_attention = attention_evaluation(record)
        if existing_attention.get("eligible"):
            continue

        distance = _market_leader_number(record, "vwap_distance_pct")
        relation = str(record.get("vwap_relation") or "").strip().lower()
        alignment = int(
            _market_leader_number(record, "alignment_score", default=0.0) or 0
        )

        if distance is not None and distance > 5.0:
            state = "WAIT FOR RESET"
            guidance = (
                "Dominant current mover, but extended above VWAP. Keep the chart "
                "available; do not chase. Reassess only after a constructive reset."
            )
        elif relation != "above" or alignment < 2:
            state = "STRUCTURE NOT READY"
            guidance = (
                "Dominant current mover with incomplete structure. Keep it on radar "
                "while 30s → 1m → 3m alignment develops; normal qualification remains closed."
            )
        else:
            state = "TRACK RE-IGNITION"
            guidance = (
                "Dominant current mover returning toward workable structure. Keep it "
                "visible; normal qualification still decides whether any trade is justified."
            )

        event = {
            "symbol": symbol,
            "state": state,
            "pct_change": round(pct_change, 1),
            "dollar_volume": round(dollar_volume, 0),
            "dominance": round(dominance, 1),
            "vwap_distance_pct": None if distance is None else round(distance, 1),
            "alignment_score": alignment,
            "guidance": guidance,
            "provenance": provenance,
        }
        choices.append(((dominance, pct_change, dollar_volume), record, event))

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def market_leader_markup(event: dict) -> str:
    """Render GS443's watch-only continuity strip."""
    distance = event.get("vwap_distance_pct")
    vwap_text = (
        "VWAP distance unavailable"
        if distance is None
        else f"{abs(float(distance)):.1f}% {'above' if float(distance) >= 0 else 'below'} VWAP"
    )
    return (
        "<div style='background:#0b1119;border:1px solid #36566f;border-radius:12px;"
        "margin:8px 0 14px;padding:10px 12px'>"
        "<div style='font-size:.76rem;letter-spacing:.09em;font-weight:950;color:#7dd3fc'>"
        "MARKET LEADER RADAR · WATCH ONLY · NO ENTRY AUTHORITY</div>"
        f"<div style='margin-top:5px;font-weight:900;color:#e6f4ff'>{html.escape(str(event['symbol']))}"
        f" · {html.escape(str(event['state']))}</div>"
        f"<div style='color:#c7d7e5;font-size:.86rem;margin-top:3px'>"
        f"Move +{float(event['pct_change']):.1f}% · Dominance {float(event['dominance']):.1f}/100 · "
        f"Alignment {int(event['alignment_score'])}/3 · {html.escape(vwap_text)}</div>"
        f"<div style='color:#93a4b8;font-size:.81rem;margin-top:5px'>{html.escape(str(event['guidance']))}</div>"
        "</div>"
    )


def install_market_leader_continuity() -> None:
    """Bind GS443 at its historical presentation position."""
    from mide import ui

    current = ui.render_walter_mission_control
    if getattr(current, _MARKET_LEADER_CONTINUITY_OWNER, False):
        return

    def render_walter_mission_control(records: list[dict]) -> None:
        result = current(records)
        if not _in_streamlit_run():
            return result
        mission = ui.walter_mission_control(records)
        _record, event = market_leader_candidate(records, mission=mission)
        if event is not None:
            ui.st.markdown(market_leader_markup(event), unsafe_allow_html=True)
        return result

    _inherit_audio_wrapper(render_walter_mission_control, current)
    render_walter_mission_control._gs443_market_leader_radar_continuity = True
    render_walter_mission_control._gs443_original = current
    setattr(
        render_walter_mission_control,
        _MARKET_LEADER_CONTINUITY_OWNER,
        True,
    )
    ui.render_walter_mission_control = render_walter_mission_control


# ---------------------------------------------------------------------------
# Authoritative extreme-mover presentation semantics
# ---------------------------------------------------------------------------
#
# GS333 remains the base extraordinary-event detector for now. GS465 and GS495 no
# longer stack wrappers around it: one Presentation + Audio wrapper owns their staged
# semantic corrections, while GS466's awareness-only stale-bar exception also lives
# here.

ANTI_CHASE_VWAP_DISTANCE_PCT = 2.0
_EXTREME_EVENT_OWNER = "_walter_next_extreme_event_semantics_owner"
_EXTREME_SELECTION_OWNER = "_walter_next_extreme_selection_continuity_owner"
_EXTREME_AWARENESS_REASON_OWNER = "_walter_gs466_extreme_awareness_reason_owner"
_EXTREME_AWARENESS_VISIBLE_OWNER = "_walter_gs466_extreme_awareness_visible_owner"


def _specific_extreme_look_now(view: dict) -> bool:
    from mide import gs310_unified_opportunity_state as unified

    if str(view.get("state") or "") != unified.LOOK_NOW:
        return False
    reason = str(view.get("reason") or "").strip().lower()
    generic = (
        "a current attention trigger says this symbol deserves a chart review",
        "current market-attention leader",
    )
    return bool(reason and not any(text in reason for text in generic))


def _cleaned_extreme_value(event: dict | None, record: dict) -> dict | None:
    """Apply GS465 truthful-label semantics to an already-detected extreme event."""
    if not event:
        return event
    if event.get("halted") or "DO NOT CHASE" in str(event.get("label") or "").upper():
        return event

    from mide import gs310_unified_opportunity_state as unified

    try:
        view = unified.opportunity_state(record)
    except Exception:
        view = {}
    state = str(view.get("state") or "")

    cleaned = dict(event)
    if state == unified.WATCH_FOR_ENTRY:
        cleaned["label"] = "EXTREME MOVER · WATCH FOR ENTRY"
        cleaned["guidance"] = (
            "The normal opportunity state has earned WATCH FOR ENTRY. Use the same "
            "entry evidence and risk discipline as any other setup."
        )
    elif _specific_extreme_look_now(view):
        cleaned["label"] = "EXTREME MOVER · LOOK NOW"
        cleaned["guidance"] = (
            "Current structure independently earned LOOK NOW; the large percentage "
            "move is context, not the reason for urgency."
        )
    else:
        cleaned["label"] = "EXTREME MOVER · WATCH"
        cleaned["guidance"] = (
            "Major mover worth monitoring, but the current structure has not earned "
            "LOOK NOW. Let normal VWAP/ST/ignition evidence promote it."
        )
    return cleaned


def cleaned_extreme_event(original, record: dict) -> dict | None:
    """Compatibility helper preserving GS465's original callable contract."""
    return _cleaned_extreme_value(original(record), record)


def _anti_chase_extreme_value(event: dict | None) -> dict | None:
    """Apply GS495's <=2% VWAP working-zone qualifier to a final extreme event."""
    if not isinstance(event, dict):
        return event
    label = str(event.get("label") or "").upper()
    if event.get("halted") or "DO NOT CHASE" in label:
        return event

    try:
        distance = float(event.get("vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None

    if (
        distance is None
        or distance <= ANTI_CHASE_VWAP_DISTANCE_PCT
        or "LOOK NOW" not in label
    ):
        return event

    view = deepcopy(event)
    view["label"] = "EXTREME MOVER · LOOK NOW · EXTENDED / WATCH RESET"
    view["guidance"] = (
        "Urgent attention only. Price is outside Walter's <=2% VWAP working zone; "
        "do not chase. Keep the chart visible and wait for a constructive reset "
        "toward VWAP before reconsidering."
    )
    view["anti_chase_active"] = True
    view["entry_authority_changed"] = False
    return view


def truthful_extreme_market_event(original, record: dict) -> dict | None:
    """Compatibility helper preserving GS495's original callable contract."""
    return _anti_chase_extreme_value(original(record))


def activate_extreme_event_stage(stage: str) -> None:
    """Activate GS465/GS495 meaning inside one authoritative extreme-event wrapper."""
    if stage not in {"cleanup", "anti_chase"}:
        raise ValueError(f"unknown extreme-event stage: {stage}")

    from mide import gs333_extreme_mover_operator_priority as gs333

    current = gs333.extreme_market_event
    if getattr(current, _EXTREME_EVENT_OWNER, False):
        wrapper = current
    else:
        baseline = current

        @wraps(baseline)
        def extreme_market_event(record: dict) -> dict | None:
            event = baseline(record)
            active = set(
                getattr(
                    extreme_market_event,
                    "_walter_next_extreme_event_stages",
                    set(),
                )
            )
            if "cleanup" in active:
                event = _cleaned_extreme_value(event, record)
            if "anti_chase" in active:
                event = _anti_chase_extreme_value(event)
            return event

        _inherit_audio_wrapper(extreme_market_event, baseline)
        setattr(extreme_market_event, _EXTREME_EVENT_OWNER, True)
        extreme_market_event._walter_next_extreme_event_stages = set()
        extreme_market_event._walter_next_extreme_event_baseline = baseline
        gs333.extreme_market_event = extreme_market_event
        wrapper = extreme_market_event

    active = set(getattr(wrapper, "_walter_next_extreme_event_stages", set()))
    active.add(stage)
    wrapper._walter_next_extreme_event_stages = active

    if stage == "cleanup":
        wrapper._gs465_presentation_priority_cleanup = True
        if not hasattr(wrapper, "_gs465_original"):
            wrapper._gs465_original = getattr(
                wrapper, "_walter_next_extreme_event_baseline", None
            )
    else:
        wrapper._gs495_extreme_attention_anti_chase_semantics = True
        if not hasattr(wrapper, "_gs495_original"):
            wrapper._gs495_original = getattr(
                wrapper, "_walter_next_extreme_event_baseline", None
            )


def _non_extreme_actionable_symbols(
    rows: list[dict],
    extreme_symbols: set[str],
) -> set[str]:
    from mide import gs310_unified_opportunity_state as unified

    priority_states = {
        unified.WATCH_FOR_ENTRY,
        unified.LOOK_NOW,
        unified.DEVELOPING,
    }
    symbols: set[str] = set()
    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in extreme_symbols:
            continue
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            continue
        if state in priority_states:
            symbols.add(symbol)
    return symbols


def prioritized_extreme_with_watch_continuity(original, records, *, now=None):
    """Preserve GS465's generic extreme-WATCH single-banner continuity."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    rows = list(records or [])
    if now is None:
        selected = original(rows)
    else:
        try:
            selected = original(rows, now=now)
        except TypeError:
            selected = original(rows)
    if selected and selected[0] is not None:
        return selected

    events: list[tuple[dict, dict]] = []
    extreme_symbols: set[str] = set()
    for record in rows:
        event = extreme.extreme_market_event(record)
        if not event:
            continue
        symbol = str(event.get("symbol") or record.get("symbol") or "").strip().upper()
        if symbol:
            extreme_symbols.add(symbol)
        events.append((record, event))

    if _non_extreme_actionable_symbols(rows, extreme_symbols):
        return None, None

    choices: list[tuple[tuple[float, float], dict, dict]] = []
    for record, event in events:
        if str(event.get("label") or "").upper() != "EXTREME MOVER · WATCH":
            continue
        try:
            pct_change = float(event.get("pct_change") or 0.0)
        except (TypeError, ValueError):
            pct_change = 0.0
        try:
            dollar_volume = float(record.get("dollar_volume") or 0.0)
        except (TypeError, ValueError):
            dollar_volume = 0.0
        choices.append(((pct_change, dollar_volume), record, event))

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def install_extreme_selection_continuity() -> None:
    """Bind GS465's selection fallback once at its historical install point."""
    from mide import gs333_extreme_mover_operator_priority as gs333

    current = gs333.prioritized_extreme_event
    if getattr(current, _EXTREME_SELECTION_OWNER, False):
        return

    @wraps(current)
    def prioritized_extreme_event(records, *, now=None):
        return prioritized_extreme_with_watch_continuity(current, records, now=now)

    _inherit_audio_wrapper(prioritized_extreme_event, current)
    prioritized_extreme_event._gs465_presentation_priority_cleanup = True
    prioritized_extreme_event._gs465_original = current
    setattr(prioritized_extreme_event, _EXTREME_SELECTION_OWNER, True)
    gs333.prioritized_extreme_event = prioritized_extreme_event


def _source_bar_stale_reason(reason: str) -> bool:
    return str(reason or "").strip().lower().startswith("source bar is ")


def extreme_awareness_continuity(record: dict, *, base_reason: str) -> bool:
    """Keep a current extreme mover visible when only its source-bar age is stale."""
    if not _source_bar_stale_reason(base_reason):
        return False
    try:
        from mide.gs333_extreme_mover_operator_priority import extreme_market_event

        return extreme_market_event(record) is not None
    except Exception:
        return False


def install_extreme_awareness_continuity() -> None:
    """Bind GS466's awareness-only stale-bar exception at its historical position."""
    from mide import gs373_operator_visibility_freshness as freshness

    current_reason = freshness.operator_visibility_reason
    if not getattr(current_reason, _EXTREME_AWARENESS_REASON_OWNER, False):
        original_reason = current_reason

        def operator_visibility_reason(record: dict) -> str:
            reason = original_reason(record)
            if extreme_awareness_continuity(record, base_reason=reason):
                return ""
            return reason

        operator_visibility_reason._gs466_extreme_awareness_continuity = True
        operator_visibility_reason._gs466_original = original_reason
        setattr(
            operator_visibility_reason,
            _EXTREME_AWARENESS_REASON_OWNER,
            True,
        )
        freshness.operator_visibility_reason = operator_visibility_reason

    current_visible = freshness.operator_visible
    if not getattr(current_visible, _EXTREME_AWARENESS_VISIBLE_OWNER, False):
        def operator_visible(record: dict) -> bool:
            return not freshness.operator_visibility_reason(record)

        operator_visible._gs466_extreme_awareness_continuity = True
        operator_visible._gs466_original = current_visible
        setattr(operator_visible, _EXTREME_AWARENESS_VISIBLE_OWNER, True)
        freshness.operator_visible = operator_visible


# ---------------------------------------------------------------------------
# GS473 fresh operator-attention audio
# ---------------------------------------------------------------------------

_OPERATOR_ATTENTION_AUDIO_OWNER = (
    "_walter_gs473_operator_attention_audio_owner"
)


def operator_attention_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def operator_attention_decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def operator_attention_field(
    record: dict,
    key: str,
    default=None,
):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return operator_attention_decision(record).get(
        key,
        default,
    )


def operator_attention_normalized(value: Any) -> str:
    return " ".join(
        str(value or "").strip().upper().split()
    )


def operator_attention_label(record: dict) -> bool:
    from mide import gs473_operator_attention_audio as gs473

    return bool(
        operator_attention_normalized(
            operator_attention_field(record, "status")
        )
        == gs473.ATTENTION_STATUS
        or operator_attention_normalized(
            operator_attention_field(
                record,
                "candidate_status",
            )
        )
        == gs473.ATTENTION_CANDIDATE
    )


def legacy_operator_attention_gate_passed(
    record: dict,
    name: str,
) -> bool:
    value = record.get(name)
    if not isinstance(value, dict):
        value = operator_attention_decision(record).get(
            name
        ) or {}
    return (
        isinstance(value, dict)
        and value.get("passed") is True
    )


def operator_attention_timeframes(record: dict) -> dict:
    value = record.get("timeframes")
    if not isinstance(value, dict):
        value = operator_attention_decision(record).get(
            "timeframes"
        ) or {}
    return value if isinstance(value, dict) else {}


def operator_attention_supportive(
    record: dict,
    label: str,
) -> bool:
    detail = (
        operator_attention_timeframes(record).get(label)
        or {}
    )
    if (
        not isinstance(detail, dict)
        or detail.get("data_available") is False
    ):
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


def operator_attention_cascade(
    record: dict,
) -> tuple[str, ...]:
    if all(
        operator_attention_supportive(record, label)
        for label in ("30s", "1m", "3m")
    ):
        return ("30s", "1m", "3m")
    if all(
        operator_attention_supportive(record, label)
        for label in ("1m", "3m", "5m")
    ):
        return ("1m", "3m", "5m")
    return ()


def previous_operator_attention(record: dict) -> bool:
    previous = record.get(
        "opportunity_pulse_previous"
    ) or {}
    if not isinstance(previous, dict) or not previous:
        return False
    return operator_attention_label(previous)


def operator_attention_candidate(record: dict) -> dict:
    """Return presentation-only LOOK NOW truth from existing evidence."""
    from mide import gs473_operator_attention_audio as gs473

    cascade = operator_attention_cascade(record)
    active = bool(
        operator_attention_label(record)
        and gs473._gate_passed(
            record,
            "participation_gate",
        )
        and gs473._gate_passed(
            record,
            "structure_gate",
        )
        and cascade
    )
    fresh = bool(
        active and not previous_operator_attention(record)
    )
    distance = operator_attention_number(
        operator_attention_field(
            record,
            "vwap_distance_pct",
        )
    )
    return {
        "active": active,
        "fresh": fresh,
        "symbol": str(
            record.get("symbol")
            or operator_attention_decision(record).get(
                "symbol"
            )
            or ""
        ).upper(),
        "cascade": list(cascade),
        "vwap_distance_pct": distance,
        "qualified_for_entry": bool(
            record.get("qualified_for_entry") is True
        ),
        "qualified_for_alert": bool(
            record.get("qualified_for_alert") is True
        ),
        "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }


def operator_attention_cascade_phrase(
    labels: list[str],
) -> str:
    if not labels:
        return (
            "multi-timeframe structure is bullish above VWAP"
        )
    if len(labels) == 1:
        joined = labels[0]
    elif len(labels) == 2:
        joined = f"{labels[0]} and {labels[1]}"
    else:
        joined = (
            ", ".join(labels[:-1])
            + f", and {labels[-1]}"
        )
    return f"{joined} are bullish above VWAP"


def operator_attention_audio_phrase(
    records: list[dict],
) -> str:
    """Speak one fresh attention cue without implying entry authority."""
    candidates = []
    for record in records or []:
        detail = operator_attention_candidate(record)
        if detail.get("fresh") and detail.get("symbol"):
            candidates.append((record, detail))
    if not candidates:
        return ""

    _record, detail = candidates[0]
    symbol = detail["symbol"]
    phrase = (
        f"{symbol}. LOOK NOW. "
        f"{operator_attention_cascade_phrase(detail['cascade'])}."
    )
    distance = detail.get("vwap_distance_pct")
    if distance is not None and distance > 5.0:
        phrase += (
            f" Extended {distance:.1f} percent above VWAP. "
            "Do not chase; watch for a reset."
        )
    elif not detail.get("qualified_for_alert"):
        phrase += (
            " Attention only; entry is not authorized yet."
        )
    return phrase


def install_operator_attention_audio() -> None:
    """Bind GS473 outside existing escalation audio at its historical point."""
    from mide import escalation

    current = escalation.escalation_alert_phrase
    if getattr(
        current,
        _OPERATOR_ATTENTION_AUDIO_OWNER,
        False,
    ):
        return

    @wraps(current)
    def escalation_alert_phrase(
        records: list[dict],
    ) -> str:
        from mide import gs473_operator_attention_audio as gs473

        established = current(records)
        if established:
            return established
        return gs473.operator_attention_audio_phrase(
            records
        )

    _inherit_audio_wrapper(
        escalation_alert_phrase,
        current,
    )
    escalation_alert_phrase._gs473_operator_attention_audio = True
    escalation_alert_phrase._gs473_original = current
    setattr(
        escalation_alert_phrase,
        _OPERATOR_ATTENTION_AUDIO_OWNER,
        True,
    )
    escalation.escalation_alert_phrase = (
        escalation_alert_phrase
    )


FRESH_3M_SECONDS = 180.0
_MATURATION_AUDIO_OWNER = "_walter_gs492_maturation_transition_audio"
_AUDIO_GATE_BRIDGE_OWNER = "_walter_gs512_audio_architecture_gate_bridge"

_AUDIO_STAGE_BY_GATE = {
    "participation_gate": "Participation Assessment",
    "structure_gate": "Expansion Assessment",
}


def _audio_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _audio_decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _audio_field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _audio_decision(record).get(key, default)


def _audio_normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _maturation_attention_label(record: dict) -> bool:
    return bool(
        _audio_normalized(_audio_field(record, "status")) == "WATCH NOW"
        or _audio_normalized(_audio_field(record, "candidate_status")) == "ENTRY READY"
    )


def _previous_maturation_attention(record: dict) -> bool:
    previous = record.get("opportunity_pulse_previous") or {}
    return (
        isinstance(previous, dict)
        and bool(previous)
        and _maturation_attention_label(previous)
    )


def _legacy_audio_gate_passed(record: dict, name: str) -> bool:
    value = record.get(name)
    if not isinstance(value, dict):
        value = _audio_decision(record).get(name) or {}
    return isinstance(value, dict) and value.get("passed") is True


# Deliberately starts with the historical GS492 rule. GS512's compatibility install
# rebinds this at its original position after the maturation-audio layer exists.
_maturation_gate_passed = _legacy_audio_gate_passed


def authoritative_gate_passed(record: dict, name: str) -> bool:
    """Resolve audio gate truth from explicit dictionaries, then Architecture-v1 audit."""
    direct = record.get(name)
    if isinstance(direct, dict) and "passed" in direct:
        return direct.get("passed") is True

    evidence = record.get("decision_time_evidence") or {}
    if isinstance(evidence, dict):
        nested = evidence.get(name)
        if isinstance(nested, dict) and "passed" in nested:
            return nested.get("passed") is True

    stage = _AUDIO_STAGE_BY_GATE.get(str(name))
    if not stage:
        return False

    from mide.gs303_flight_recorder_authoritative_funnel import _gate_from_audit, _stage_audit

    compatibility = _gate_from_audit(_stage_audit(record, stage))
    return compatibility.get("passed") is True


def _maturation_timeframes(record: dict) -> dict:
    value = record.get("timeframes")
    if not isinstance(value, dict):
        value = _audio_decision(record).get("timeframes") or {}
    return value if isinstance(value, dict) else {}


def _maturation_tf(record: dict, label: str) -> dict:
    detail = _maturation_timeframes(record).get(label) or {}
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


def _maturation_cross_new(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    cross = raw.get("st_vwap_line_cross") or {}
    return isinstance(cross, dict) and cross.get("new") is True


def _three_minute_maturation_fresh(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    age = _audio_number(raw.get("bullish_flip_age_seconds"))
    return bool(age is not None and 0.0 <= age <= FRESH_3M_SECONDS)


def maturation_transition(record: dict) -> dict:
    """Return presentation-only runner maturation truth from current evidence."""
    thirty = _maturation_tf(record, "30s")
    one = _maturation_tf(record, "1m")
    three = _maturation_tf(record, "3m")
    gates = bool(
        _maturation_gate_passed(record, "participation_gate")
        and _maturation_gate_passed(record, "structure_gate")
    )
    two_rung = bool(thirty.get("supportive") and one.get("supportive"))
    three_rung = bool(two_rung and three.get("supportive"))
    structure_fresh = bool(
        _three_minute_maturation_fresh(three)
        or _maturation_cross_new(thirty)
        or _maturation_cross_new(one)
    )

    stage = "NONE"
    if gates and three_rung and structure_fresh:
        stage = "RUNNER_DETECTED"
    elif (
        gates
        and two_rung
        and _maturation_attention_label(record)
        and not _previous_maturation_attention(record)
    ):
        stage = "RUNNER_BUILDING"

    return {
        "active": stage != "NONE",
        "stage": stage,
        "symbol": str(
            record.get("symbol") or _audio_decision(record).get("symbol") or ""
        ).strip().upper(),
        "gates_passed": gates,
        "thirty_second_supportive": bool(thirty.get("supportive")),
        "one_minute_supportive": bool(one.get("supportive")),
        "three_minute_supportive": bool(three.get("supportive")),
        "structure_fresh": structure_fresh,
        "vwap_distance_pct": _audio_number(_audio_field(record, "vwap_distance_pct")),
        "qualified_for_entry": bool(_audio_field(record, "qualified_for_entry") is True),
        "qualified_for_alert": bool(_audio_field(record, "qualified_for_alert") is True),
        "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }


def maturation_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh runner-maturation event without granting entry authority."""
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


def install_maturation_transition_audio() -> None:
    """Bind maturation-event audio at the historical GS492 position."""
    from mide import escalation
    from mide.gs365_chime_semantic_classifier import semantic_chime_count

    current = escalation.escalation_alert_phrase
    if getattr(current, _MATURATION_AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        established = current(rows)
        if established and semantic_chime_count(established) >= 3:
            return established
        maturation = maturation_audio_phrase(rows)
        return maturation or established

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs492_maturation_transition_audio = True
    alert_phrase._gs492_original = current
    setattr(alert_phrase, _MATURATION_AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


def install_audio_architecture_gate_bridge() -> None:
    """Activate Architecture-v1 gate fallback at the historical GS512 position."""
    global _maturation_gate_passed

    from mide import gs473_operator_attention_audio as gs473

    _maturation_gate_passed = authoritative_gate_passed
    gs473._gate_passed = authoritative_gate_passed


_LEADER_RESET_AUDIO_OWNER = "_walter_gs477_leader_reset_audio_owner"


def augment_leader_reset_records(records: list[dict], visible: list[dict]) -> list[dict]:
    """Keep an active reset/re-ignition visible as awareness only when needed."""
    from mide.gs375_operator_awareness import awareness_record

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
    from mide.authorities import market_evidence

    enriched = market_evidence.apply_leader_reset_marks(records)
    visible = list(actionable_function(enriched) or [])
    return augment_leader_reset_records(enriched, visible)


def leader_reset_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh reset transition without implying a trade instruction."""
    from mide.authorities import market_evidence

    for record in records or []:
        evidence = record.get("leader_reset_reignition") or {}
        if not evidence.get("stage_fresh"):
            continue
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        stage = evidence.get("stage")
        if stage == market_evidence.RESET_WATCH:
            distance = abs(float(evidence.get("current_vwap_distance_pct") or 0.0))
            return (
                f"{symbol}. RESET WATCH. Proven leader is back within {distance:.1f} percent "
                "of VWAP with 30 second and 1 minute SuperTrend bullish. Watch the reclaim. "
                "Attention only."
            )
        if stage == market_evidence.THREE_MINUTE_CONFIRMATION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed and the 3 minute "
                "SuperTrend rung is confirmed. Attention only; entry is not authorized by this cue."
            )
        if stage == market_evidence.REIGNITION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed with 30 second and "
                "1 minute SuperTrend bullish and active flow. 3 minute confirmation pending."
            )
    return ""


def _inherit_audio_wrapper(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install_leader_reset_audio() -> None:
    """Bind leader-reset audio at the historical GS477 audio position."""
    from mide import escalation
    from mide.authorities import market_evidence

    current = escalation.escalation_alert_phrase
    if getattr(current, _LEADER_RESET_AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        enriched = market_evidence.apply_leader_reset_marks(records)
        established = current(records)
        if established:
            return established
        return leader_reset_audio_phrase(enriched)

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs477_leader_reset_reignition = True
    alert_phrase._gs477_original = current
    setattr(alert_phrase, _LEADER_RESET_AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


# ---------------------------------------------------------------------------
# GS459 price-trajectory operator attention
# ---------------------------------------------------------------------------

PRICE_TRAJECTORY_BAND = 38
PRICE_TRAJECTORY_MIN_3M_CHANGE_PCT = 1.0
PRICE_TRAJECTORY_MIN_ACCELERATION_PCT_PER_MIN = 0.20
PRICE_TRAJECTORY_MIN_POSITIVE_CLOSE_RATIO = 0.60
PRICE_TRAJECTORY_MAX_GIVEBACK_FROM_5M_HIGH_PCT = 1.50
PRICE_TRAJECTORY_MIN_FLOW_ACCELERATION = 1.20
PRICE_TRAJECTORY_MIN_PARTICIPATION_SCORE = 40.0
_PRICE_TRAJECTORY_ORDER_OWNER = "_walter_gs459_price_trajectory_attention_owner"


def _trajectory_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _trajectory_supporting_flow(record: dict) -> bool:
    participation = _trajectory_number(
        record.get(
            "participation_surge_score",
            record.get("participation_score", 0.0),
        )
    )
    accelerations = (
        _trajectory_number(
            record.get(
                "volume_acceleration_3m",
                record.get("volume_acceleration", 0.0),
            )
        ),
        _trajectory_number(
            record.get(
                "volume_acceleration_5m",
                record.get("acceleration_ratio", 0.0),
            )
        ),
        _trajectory_number(record.get("dollar_flow_acceleration_3m", 0.0)),
        _trajectory_number(
            record.get(
                "dollar_flow_acceleration_5m",
                record.get("dollar_flow_acceleration", 0.0),
            )
        ),
    )
    return bool(
        max(accelerations) >= PRICE_TRAJECTORY_MIN_FLOW_ACCELERATION
        or participation >= PRICE_TRAJECTORY_MIN_PARTICIPATION_SCORE
        or record.get("volume_above_preceding_15m_pace")
        or record.get("broke_previous_15m_high_with_volume")
    )


def trajectory_attention(record: dict) -> dict:
    """Return operator-only price-path ignition evidence."""
    from mide import gs310_unified_opportunity_state as unified

    state = str(unified.opportunity_state(record).get("state") or "")
    available = bool(record.get("price_trajectory_available"))
    change_3m = _trajectory_number(record.get("price_change_3m_pct"))
    change_5m = _trajectory_number(record.get("price_change_5m_path_pct"))
    acceleration = _trajectory_number(
        record.get("price_path_acceleration_pct_per_min")
    )
    persistence = _trajectory_number(
        record.get("positive_close_ratio_5m")
    )
    giveback = _trajectory_number(
        record.get("giveback_from_5m_high_pct"),
        default=999.0,
    )
    flow = _trajectory_supporting_flow(record)
    structure = bool(record.get("higher_lows") or record.get("near_hod"))

    signal = bool(
        available
        and state != unified.HALTED
        and change_3m >= PRICE_TRAJECTORY_MIN_3M_CHANGE_PCT
        and acceleration
        >= PRICE_TRAJECTORY_MIN_ACCELERATION_PCT_PER_MIN
        and persistence >= PRICE_TRAJECTORY_MIN_POSITIVE_CLOSE_RATIO
        and giveback
        <= PRICE_TRAJECTORY_MAX_GIVEBACK_FROM_5M_HIGH_PCT
        and flow
        and structure
    )
    return {
        "active": signal,
        "state": state,
        "reason": (
            "accelerating_price_path"
            if signal
            else "no_trajectory_ignition"
        ),
        "change_3m_pct": change_3m,
        "change_5m_pct": change_5m,
        "acceleration_pct_per_min": acceleration,
        "positive_close_ratio_5m": persistence,
        "giveback_from_5m_high_pct": giveback,
        "supporting_flow": flow,
        "structure_support": structure,
    }


def effective_trajectory_attention_band(record: dict) -> int:
    """Insert trajectory ignition below LOOK NOW and above older/developing bands."""
    from mide import gs459_price_trajectory_attention as gs459

    base = int(_maturation_attention_compat(record).get("band") or 0)
    if gs459.trajectory_attention(record).get("active"):
        return max(base, PRICE_TRAJECTORY_BAND)
    return base


def ordered_trajectory_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    """Preserve GS457 ordering except for the narrow trajectory priority lift."""
    from mide import gs457_maturation_leader_priority as gs457
    from mide import gs459_price_trajectory_attention as gs459

    baseline = (
        list(baseline_order(records))
        if baseline_order is not None
        else gs457.ordered_maturation_records(records)
    )

    def trajectory_tie(record: dict) -> tuple:
        detail = gs459.trajectory_attention(record)
        if not detail.get("active"):
            return (float("-inf"), float("-inf"), float("-inf"))
        return (
            float(detail.get("acceleration_pct_per_min") or 0.0),
            float(detail.get("change_3m_pct") or 0.0),
            float(detail.get("positive_close_ratio_5m") or 0.0),
        )

    baseline.sort(key=trajectory_tie, reverse=True)
    baseline.sort(
        key=gs459.effective_attention_band,
        reverse=True,
    )
    return baseline


def install_price_trajectory_presentation() -> None:
    """Install GS459's presentation-only operator-order lift."""
    from mide import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _PRICE_TRAJECTORY_ORDER_OWNER, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        from mide import gs459_price_trajectory_attention as gs459

        return gs459.ordered_trajectory_records(
            records,
            baseline_order=current,
        )

    _inherit_audio_wrapper(ordered_escalation_records, current)
    ordered_escalation_records._gs459_price_trajectory_attention = True
    ordered_escalation_records._gs459_original = current
    setattr(
        ordered_escalation_records,
        _PRICE_TRAJECTORY_ORDER_OWNER,
        True,
    )
    gs369.ordered_escalation_records = ordered_escalation_records


# ---------------------------------------------------------------------------
# GS455 ordered maturation presentation / audio
# ---------------------------------------------------------------------------
#
# Market Evidence owns the maturation signal and Thesis / State owns its state meaning.
# Presentation + Audio owns the operator change record and spoken alert priority. The
# historical gs455 module remains the mutable compatibility seam so retained runtimes
# and regression monkeypatches continue to observe the same callable names.


def progression_change(record: dict) -> dict | None:
    """Describe one fresh GS455 maturation-rung transition for operator alerting."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    signal = gs455.progression_signal(record)
    if not signal.get("active"):
        return None
    symbol = str(
        record.get("symbol") or ""
    ).strip().upper()
    if not symbol:
        return None
    rung = str(
        signal.get("new_rung") or ""
    ).upper()
    stamp = str(
        signal.get("timestamp") or "unknown"
    )
    return {
        "symbol": symbol,
        "from": f"{rung} CROSS@{stamp}",
        "to": f"ST/VWAP MATURATION {rung}",
    }


def spoken_progression_rung(label: str) -> str:
    return {
        "30s": "30 second",
        "1m": "1 minute",
        "3m": "3 minute",
        "5m": "5 minute",
        "10m": "10 minute",
        "15m": "15 minute",
    }.get(label, label)


def progression_audio_phrase(
    records: list[dict],
) -> str:
    """Return the historical tier-2 GS455 maturation phrase."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    choices = []
    for record in records or []:
        signal = gs455.progression_signal(
            record
        )
        if signal.get("active"):
            try:
                rank = gs455.CROSSOVER_LADDER.index(
                    signal["new_rung"]
                )
            except (ValueError, KeyError):
                continue
            choices.append(
                (rank, record, signal)
            )
    if not choices:
        return ""

    _, record, signal = max(
        choices,
        key=lambda item: item[0],
    )
    symbol = (
        str(
            record.get("symbol")
            or "Symbol"
        ).strip().upper()
        or "SYMBOL"
    )
    rung = gs455._spoken_rung(
        str(
            signal.get("new_rung")
            or ""
        )
    )
    stage = str(
        signal.get("stage") or ""
    ).lower()
    phrase = (
        f"{symbol}. LOOK NOW. SuperTrend VWAP maturation "
        f"reached {rung}. {stage.capitalize()} advancing."
    )
    distance = signal.get(
        "vwap_distance_pct"
    )
    if (
        distance is not None
        and distance
        > gs455.LOOK_NOW_MAX_VWAP_DISTANCE_PCT
    ):
        phrase += " Extended. Do not chase."
    return phrase


def install_progression_alert_priority() -> None:
    """Bind GS455 change/audio semantics at the historical alert install point."""
    from mide import escalation
    from mide import gs455_early_ignition_3m_confirmation as gs455
    from mide.gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = (
        escalation.escalation_state_changes
    )
    if not getattr(
        current_changes,
        "_gs455_crossover_progression",
        False,
    ):
        @wraps(current_changes)
        def state_changes(
            records: list[dict],
        ) -> list[dict]:
            rows = list(records or [])
            existing = list(
                current_changes(rows)
            )
            additions = [
                change
                for row in rows
                if (
                    change
                    := gs455._progression_change(
                        row
                    )
                )
            ]
            if not additions:
                return existing
            keys = {
                (
                    str(
                        item.get("symbol")
                        or ""
                    ).upper(),
                    str(
                        item.get("from")
                        or ""
                    ),
                    str(
                        item.get("to")
                        or ""
                    ),
                )
                for item in existing
            }
            for change in additions:
                key = (
                    change["symbol"],
                    change["from"],
                    change["to"],
                )
                if key not in keys:
                    existing.append(
                        change
                    )
                    keys.add(key)
            return existing

        _inherit_audio_wrapper(
            state_changes,
            current_changes,
        )
        state_changes._gs455_crossover_progression = True
        state_changes._gs455_original = (
            current_changes
        )
        escalation.escalation_state_changes = (
            state_changes
        )

    current_phrase = (
        escalation.escalation_alert_phrase
    )
    if getattr(
        current_phrase,
        "_gs455_crossover_progression",
        False,
    ):
        return

    @wraps(current_phrase)
    def alert_phrase(
        records: list[dict],
    ) -> str:
        rows = list(records or [])
        existing = str(
            current_phrase(rows) or ""
        )
        progression = (
            gs455._progression_phrase(
                rows
            )
        )
        if not progression:
            return existing
        if (
            existing
            and semantic_chime_count(
                existing
            )
            >= 3
        ):
            return existing
        return progression

    _inherit_audio_wrapper(
        alert_phrase,
        current_phrase,
    )
    alert_phrase._gs455_crossover_progression = True
    alert_phrase._gs455_original = (
        current_phrase
    )
    escalation.escalation_alert_phrase = (
        alert_phrase
    )


# ---------------------------------------------------------------------------
# GS460/GS461 ST compression + cascade runway presentation/audio
# ---------------------------------------------------------------------------

ST_FLIP_ANTI_CHASE_DISTANCE_PCT = 5.0
_ST_FLIP_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"
_CASCADE_RUNWAY_PROVENANCE = "ST_CASCADE_RUNWAY"


def _st_flip_presentation_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def state_with_st_flip_compression(original, record: dict) -> dict:
    """Apply GS460 LOOK NOW / anti-chase presentation semantics."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs460_st_flip_compression_ignition as gs460

    base = original(record)
    signal = gs460.st_flip_compression(record)
    if not signal.get("active"):
        return base
    if base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _ST_FLIP_PROVENANCE not in provenance:
        provenance.append(_ST_FLIP_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_flip_compression"] = signal

    span = signal.get("cluster_span_pct")
    sequence = signal.get("sequence") or "30s -> 1m"
    stage = str(signal.get("stage") or "IGNITION").upper()
    next_frame = signal.get("next_frame") or {}
    next_text = ""
    if next_frame.get("already_bullish"):
        next_text = f" {next_frame.get('timeframe')} is already bullish."
    elif next_frame.get("distance_to_supertrend_pct") is not None:
        next_text = (
            f" {next_frame.get('timeframe')} SuperTrend is about "
            f"{next_frame['distance_to_supertrend_pct']:.1f}% away."
        )

    distance = _st_flip_presentation_number(
        record.get("vwap_distance_pct")
    )
    if (
        distance is not None
        and distance > ST_FLIP_ANTI_CHASE_DISTANCE_PCT
    ):
        view["state"] = unified.CHASE_WAIT
        view["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
        view["reason"] = (
            f"{stage}: {sequence} ST flip prices are compressed within "
            f"{span:.1f}% with supporting flow.{next_text} "
            f"Price is already {distance:.1f}% above VWAP."
        )
        view["next_step"] = (
            "Open the chart now for ignition context, but DO NOT CHASE. "
            "Flip compression is attention evidence only; wait for the "
            "existing VWAP/readiness rules."
        )
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = (
        f"{stage}: {sequence} ST flip prices are compressed within "
        f"{span:.1f}% with supporting flow.{next_text}"
    )
    view["next_step"] = (
        "Open the chart now. This bottom-up compression can precede a "
        "timeframe cascade, but it does not grant entry authority; normal "
        "readiness and anti-chase rules remain."
    )
    return view


def st_flip_compression_change(record: dict) -> dict | None:
    from mide import gs460_st_flip_compression_ignition as gs460

    signal = gs460.st_flip_compression(record)
    if not signal.get("fresh_join"):
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    highest = str(signal.get("highest_rung") or "").upper()
    prices = signal.get("flip_prices") or {}
    fingerprint = ",".join(
        f"{label}:{prices.get(label)}"
        for label in gs460.EARLY_LADDER
        if label in prices
    )
    return {
        "symbol": symbol,
        "from": f"ST FLIP CLUSTER {fingerprint}",
        "to": f"IGNITION COMPRESSION {highest}",
    }


def st_flip_spoken(label: str) -> str:
    return {
        "30s": "30 second",
        "1m": "1 minute",
        "3m": "3 minute",
        "5m": "5 minute",
    }.get(label, label)


def st_flip_compression_phrase(records: list[dict]) -> str:
    from mide import gs460_st_flip_compression_ignition as gs460

    choices = []
    for record in records or []:
        signal = gs460.st_flip_compression(record)
        if signal.get("fresh_join"):
            choices.append(
                (int(signal.get("depth") or 0), record, signal)
            )
    if not choices:
        return ""
    _depth, record, signal = max(
        choices,
        key=lambda item: item[0],
    )
    symbol = (
        str(record.get("symbol") or "Symbol").strip().upper()
        or "SYMBOL"
    )
    highest = st_flip_spoken(
        str(signal.get("highest_rung") or "")
    )
    span = float(signal.get("cluster_span_pct") or 0.0)
    phrase = (
        f"{symbol}. LOOK NOW. Ignition compression. SuperTrend flips "
        f"through {highest} are clustered within {span:.1f} percent "
        "with supporting flow."
    )
    distance = _st_flip_presentation_number(
        record.get("vwap_distance_pct")
    )
    if (
        distance is not None
        and distance > ST_FLIP_ANTI_CHASE_DISTANCE_PCT
    ):
        phrase += " Extended. Do not chase."
    return phrase


def install_st_flip_compression_state() -> None:
    """Install GS460 operator-state semantics at the historical boundary."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs460_st_flip_compression", False):
        calibrated = current
    else:
        original = current

        @wraps(original)
        def calibrated(record: dict) -> dict:
            return state_with_st_flip_compression(original, record)

        _inherit_audio_wrapper(calibrated, current)
        calibrated._gs460_st_flip_compression = True
        calibrated._gs460_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def install_st_flip_compression_alerts() -> None:
    """Install GS460 state-change and tier-2 audio semantics."""
    from mide import escalation
    from mide.gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = escalation.escalation_state_changes
    if not getattr(
        current_changes,
        "_gs460_st_flip_compression",
        False,
    ):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            existing = list(current_changes(rows))
            additions = [
                change
                for row in rows
                if (change := st_flip_compression_change(row))
            ]
            keys = {
                (
                    str(item.get("symbol") or "").upper(),
                    str(item.get("from") or ""),
                    str(item.get("to") or ""),
                )
                for item in existing
            }
            for change in additions:
                key = (
                    change["symbol"],
                    change["from"],
                    change["to"],
                )
                if key not in keys:
                    existing.append(change)
                    keys.add(key)
            return existing

        _inherit_audio_wrapper(state_changes, current_changes)
        state_changes._gs460_st_flip_compression = True
        state_changes._gs460_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if getattr(
        current_phrase,
        "_gs460_st_flip_compression",
        False,
    ):
        return

    @wraps(current_phrase)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        existing = str(current_phrase(rows) or "")
        compression = st_flip_compression_phrase(rows)
        if not compression:
            return existing
        if existing and semantic_chime_count(existing) >= 3:
            return existing
        return compression

    _inherit_audio_wrapper(alert_phrase, current_phrase)
    alert_phrase._gs460_st_flip_compression = True
    alert_phrase._gs460_original = current_phrase
    escalation.escalation_alert_phrase = alert_phrase


def install_st_flip_compression_presentation() -> None:
    install_st_flip_compression_state()
    install_st_flip_compression_alerts()


def cascade_runway_text(runway: dict) -> str:
    if not runway.get("active"):
        return ""
    parts: list[str] = []
    contiguous = list(
        runway.get("contiguous_slower_bullish") or []
    )
    if contiguous:
        parts.append(" / ".join(contiguous) + " already bullish")
    barrier = dict(runway.get("next_barrier") or {})
    if barrier:
        label = barrier.get("timeframe")
        gap = _st_flip_presentation_number(
            barrier.get("barrier_gap_pct")
        )
        if gap is not None:
            parts.append(
                f"next {label} SuperTrend line {gap:.1f}% away"
            )
        else:
            parts.append(f"next {label} SuperTrend barrier present")
    unavailable = runway.get("blocked_by_unavailable")
    if unavailable:
        parts.append(f"{unavailable} runway not yet measurable")
    future = list(runway.get("future_bullish_support") or [])
    if future:
        parts.append(
            "later " + " / ".join(future) + " already bullish"
        )
    return "; ".join(parts)


def state_with_cascade_runway(original, record: dict) -> dict:
    base = original(record)
    runway = dict(record.get("st_cascade_runway") or {})
    if not runway.get("active"):
        return base
    provenance = list(base.get("attention_provenance") or [])
    if _ST_FLIP_PROVENANCE not in provenance:
        return base

    text = cascade_runway_text(runway)
    if not text:
        return base
    view = deepcopy(base)
    if _CASCADE_RUNWAY_PROVENANCE not in provenance:
        provenance.append(_CASCADE_RUNWAY_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_cascade_runway"] = runway
    reason = str(view.get("reason") or "").rstrip()
    if "Cascade runway:" not in reason:
        view["reason"] = (
            f"{reason} Cascade runway: {text}."
        ).strip()
    next_step = str(view.get("next_step") or "").rstrip()
    if "current SuperTrend line" not in next_step:
        view["next_step"] = (
            f"{next_step} Treat the slower-frame gap as proximity to "
            "the current SuperTrend line, not a guaranteed future "
            "flip price."
        ).strip()
    return view


def install_cascade_runway_state() -> None:
    """Install GS461 explanation enrichment without changing state."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs461_cascade_runway", False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return state_with_cascade_runway(current, record)

        _inherit_audio_wrapper(calibrated, current)
        calibrated._gs461_cascade_runway = True
        calibrated._gs461_original = current
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def cascade_runway_alert(records: list[dict]) -> str:
    from mide import gs460_st_flip_compression_ignition as gs460

    choices = []
    for record in records or []:
        compression = gs460.st_flip_compression(record)
        runway = dict(record.get("st_cascade_runway") or {})
        if (
            not compression.get("fresh_join")
            or not runway.get("active")
        ):
            continue
        barrier = dict(runway.get("next_barrier") or {})
        gap = _st_flip_presentation_number(
            barrier.get("barrier_gap_pct")
        )
        choices.append(
            (
                int(compression.get("depth") or 0),
                -(gap if gap is not None else 999.0),
                record,
                runway,
            )
        )
    if not choices:
        return ""
    _depth, _gap_rank, _record, runway = max(
        choices,
        key=lambda item: (item[0], item[1]),
    )
    text = cascade_runway_text(runway)
    return f" Cascade runway. {text}." if text else ""


def install_cascade_runway_alerts() -> None:
    from mide import escalation

    current = escalation.escalation_alert_phrase
    if getattr(current, "_gs461_cascade_runway", False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        phrase = str(current(rows) or "")
        if "IGNITION COMPRESSION" not in phrase.upper():
            return phrase
        runway = cascade_runway_alert(rows)
        if runway and "CASCADE RUNWAY" not in phrase.upper():
            return phrase.rstrip() + runway
        return phrase

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs461_cascade_runway = True
    alert_phrase._gs461_original = current
    escalation.escalation_alert_phrase = alert_phrase


def install_cascade_runway_presentation() -> None:
    install_cascade_runway_state()
    install_cascade_runway_alerts()


# ---------------------------------------------------------------------------
# GS462 pre-flip ignition presentation / operator attention
# ---------------------------------------------------------------------------

_PREFLIP_PROVENANCE = "PRE_FLIP_ST_IGNITION_WATCH"
_PREFLIP_ORDER_OWNER = "_walter_gs462_preflip_ignition_watch_owner"


def preflip_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def preflip_gap_pct(
    close: float | None,
    st_value: float | None,
) -> float | None:
    close = preflip_number(close)
    st_value = preflip_number(st_value)
    if close in (None, 0) or st_value is None:
        return None
    return abs(st_value - close) / close * 100.0


def preflip_timeframe_detail(record: dict, label: str) -> dict:
    """Describe already-computed timeframe support for GS462 attention."""
    from mide import gs462_preflip_ignition_watch as gs462

    timeframes = record.get("timeframes") or {}
    detail = dict(timeframes.get(label) or {})
    line_cross = dict(detail.get("st_vwap_line_cross") or {})

    if label == "30s":
        alignment = dict(
            (record.get("timeframe_alignment") or {}).get("30s")
            or {}
        )
        tripwire = dict(record.get("thirty_second_tripwire") or {})
        close = (
            preflip_number(tripwire.get("latest_close"))
            or preflip_number(detail.get("current_close"))
            or preflip_number(record.get("price"))
        )
        st_value = (
            preflip_number(alignment.get("supertrend_value"))
            or preflip_number(detail.get("supertrend_value"))
            or preflip_number(
                line_cross.get("latest_supertrend_value")
            )
        )
        vwap = (
            preflip_number(alignment.get("vwap_value"))
            or preflip_number(detail.get("vwap_value"))
            or preflip_number(record.get("vwap_30s_value"))
        )
        above_vwap = bool(
            alignment.get("above_vwap")
            if "above_vwap" in alignment
            else (
                close is not None
                and vwap is not None
                and close >= vwap
            )
        )
        bullish = bool(
            record.get("supertrend_30s_bullish")
            or alignment.get("supertrend_bullish")
            or detail.get("current_supertrend_bullish")
            or detail.get("supertrend")
        )
        age = (
            preflip_number(
                record.get(
                    "supertrend_30s_last_flip_age_seconds"
                )
            )
            if record.get(
                "supertrend_30s_last_flip_age_seconds"
            )
            is not None
            else preflip_number(
                tripwire.get("last_flip_age_seconds")
            )
        )
        gap = preflip_gap_pct(close, st_value)
        return {
            "timeframe": label,
            "available": bool(
                close is not None
                and (st_value is not None or bullish)
            ),
            "bullish": bullish,
            "above_vwap": above_vwap,
            "current_close": close,
            "current_supertrend": st_value,
            "current_vwap": vwap,
            "st_gap_pct": (
                round(gap, 3) if gap is not None else None
            ),
            "flip_age_seconds": age,
            "recent_flip": bool(
                bullish
                and age is not None
                and 0
                <= age
                <= float(gs462.RECENT_30S_FLIP_SECONDS)
            ),
        }

    close = (
        preflip_number(detail.get("current_close"))
        or preflip_number(record.get("price"))
    )
    st_value = preflip_number(
        line_cross.get("latest_supertrend_value")
    )
    vwap = (
        preflip_number(detail.get("current_vwap"))
        or preflip_number(
            line_cross.get("latest_vwap_value")
        )
    )
    bullish = bool(
        detail.get("current_supertrend_bullish")
        or detail.get("supertrend")
    )
    above_vwap = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    gap = preflip_gap_pct(close, st_value)
    near = bool(
        not bullish
        and gap is not None
        and gap <= float(gs462.NEAR_ST_LINE_PCT)
    )
    return {
        "timeframe": label,
        "available": bool(
            close is not None
            and (st_value is not None or bullish)
        ),
        "bullish": bullish,
        "above_vwap": above_vwap,
        "current_close": close,
        "current_supertrend": st_value,
        "current_vwap": vwap,
        "st_gap_pct": (
            round(gap, 3) if gap is not None else None
        ),
        "near_supertrend": near,
        "supportive": bool(
            above_vwap and (bullish or near)
        ),
    }


def preflip_ignition_watch(record: dict) -> dict:
    """Return GS462 early-watch / jet-fuel operator attention truth."""
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    thirty = gs462._timeframe_detail(record, "30s")
    one = gs462._timeframe_detail(record, "1m")
    three = gs462._timeframe_detail(record, "3m")
    five = gs462._timeframe_detail(record, "5m")
    ten = gs462._timeframe_detail(record, "10m")

    seed = bool(
        thirty.get("recent_flip")
        and thirty.get("above_vwap")
        and one.get("supportive")
    )
    flow = bool(gs459._supporting_flow(record))
    jet_fuel = bool(
        seed and three.get("supportive") and flow
    )
    bonus = [
        label
        for label, detail in (
            ("5m", five),
            ("10m", ten),
        )
        if detail.get("bullish")
        and detail.get("above_vwap")
    ]

    return {
        "active": seed,
        "stage": (
            "JET FUEL"
            if jet_fuel
            else "EARLY WATCH" if seed else "NONE"
        ),
        "thirty_second": thirty,
        "one_minute": one,
        "three_minute": three,
        "five_minute": five,
        "ten_minute": ten,
        "supporting_flow": flow,
        "jet_fuel": jet_fuel,
        "bonus_continuation": bonus,
        "near_st_line_limit_pct": float(
            gs462.NEAR_ST_LINE_PCT
        ),
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
        "three_minute_required_for_watch": False,
        "five_ten_required": False,
        "new_audio_added": False,
    }


def preflip_tf_phrase(label: str, detail: dict) -> str:
    if detail.get("bullish"):
        return f"{label} bullish above VWAP"
    gap = preflip_number(detail.get("st_gap_pct"))
    if (
        detail.get("near_supertrend")
        and gap is not None
    ):
        return (
            f"{label} ST line {gap:.1f}% away above VWAP"
        )
    return f"{label} not supportive"


def state_with_preflip(original, record: dict) -> dict:
    """Enrich explanation only; do not rewrite Opportunity State."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs462_preflip_ignition_watch as gs462

    base = original(record)
    signal = gs462.preflip_ignition_watch(record)
    if (
        not signal.get("active")
        or base.get("state") == unified.HALTED
    ):
        return base

    view = deepcopy(base)
    provenance = list(
        view.get("attention_provenance") or []
    )
    if _PREFLIP_PROVENANCE not in provenance:
        provenance.append(_PREFLIP_PROVENANCE)
    view["attention_provenance"] = provenance
    view["preflip_ignition_watch"] = signal

    one_text = gs462._tf_phrase(
        "1m",
        signal["one_minute"],
    )
    reason_add = (
        "EARLY ST WATCH: recent 30s bullish flip above VWAP; "
        f"{one_text}."
    )
    if signal.get("jet_fuel"):
        reason_add += (
            " JET FUEL: "
            f"{gs462._tf_phrase('3m', signal['three_minute'])} "
            "with supportive participation/flow."
        )
    elif signal["three_minute"].get("supportive"):
        reason_add += (
            " 3m is supportive, but participation/flow is not "
            "yet strong enough for the jet-fuel label."
        )
    bonus = list(
        signal.get("bonus_continuation") or []
    )
    if bonus:
        reason_add += (
            " Bonus continuation: "
            + "/".join(bonus)
            + " bullish above VWAP."
        )

    reason = str(view.get("reason") or "").rstrip()
    if "EARLY ST WATCH:" not in reason:
        view["reason"] = (
            f"{reason} {reason_add}"
        ).strip()
    next_step = str(
        view.get("next_step") or ""
    ).rstrip()
    if "30s/1m watch" not in next_step:
        view["next_step"] = (
            f"{next_step} Treat this as a 30s/1m watch only. "
            "3m adds jet fuel; 5m/10m are bonuses, not gates. "
            "Existing readiness, VWAP anti-chase and execution "
            "rules remain authoritative."
        ).strip()
    return view


def effective_preflip_attention_band(record: dict) -> int:
    """Lift GS462 attention below LOOK NOW without changing state."""
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    base = int(gs459.effective_attention_band(record))
    if gs462.preflip_ignition_watch(record).get("active"):
        return max(
            base,
            int(gs462.PRE_FLIP_ATTENTION_BAND),
        )
    return base


def ordered_preflip_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    """Preserve base order except for the bounded GS462 lift."""
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    baseline = (
        list(baseline_order(records))
        if baseline_order is not None
        else gs459.ordered_trajectory_records(records)
    )

    def tie_key(record: dict) -> tuple:
        detail = gs462.preflip_ignition_watch(record)
        if not detail.get("active"):
            return (
                0,
                float("-inf"),
                float("-inf"),
            )
        one_gap = preflip_number(
            (detail.get("one_minute") or {}).get(
                "st_gap_pct"
            )
        )
        three_gap = preflip_number(
            (detail.get("three_minute") or {}).get(
                "st_gap_pct"
            )
        )
        return (
            1 if detail.get("jet_fuel") else 0,
            -(
                one_gap
                if one_gap is not None
                else 999.0
            ),
            -(
                three_gap
                if three_gap is not None
                else 999.0
            ),
        )

    baseline.sort(key=tie_key, reverse=True)
    baseline.sort(
        key=gs462.effective_attention_band,
        reverse=True,
    )
    return baseline


def install_preflip_state() -> None:
    """Install GS462 explanation enrichment at the historical seam."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(
        current,
        "_gs462_preflip_ignition_watch",
        False,
    ):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            from mide import (
                gs462_preflip_ignition_watch as gs462,
            )

            return gs462._state_with_preflip(
                current,
                record,
            )

        _inherit_audio_wrapper(calibrated, current)
        calibrated._gs462_preflip_ignition_watch = True
        calibrated._gs462_original = current
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def install_preflip_order() -> None:
    """Install GS462's bounded operator-order lift."""
    from mide import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _PREFLIP_ORDER_OWNER, False):
        return

    def ordered_escalation_records(
        records: list[dict],
    ) -> list[dict]:
        from mide import (
            gs462_preflip_ignition_watch as gs462,
        )

        return gs462.ordered_preflip_records(
            records,
            baseline_order=current,
        )

    _inherit_audio_wrapper(
        ordered_escalation_records,
        current,
    )
    ordered_escalation_records._gs462_preflip_ignition_watch = True
    ordered_escalation_records._gs462_original = current
    setattr(
        ordered_escalation_records,
        _PREFLIP_ORDER_OWNER,
        True,
    )
    gs369.ordered_escalation_records = (
        ordered_escalation_records
    )


def install_preflip_presentation() -> None:
    """Install all GS462 Presentation + Audio responsibilities."""
    install_preflip_state()
    install_preflip_order()


# ---------------------------------------------------------------------------
# GS453 bounded constructive-extension presentation semantics
# ---------------------------------------------------------------------------

CONSTRUCTIVE_EXTENSION_MIN_VWAP_DISTANCE_PCT = 2.0
CONSTRUCTIVE_EXTENSION_MAX_VWAP_DISTANCE_PCT = 5.0
CONSTRUCTIVE_EXTENSION_MIN_ALIGNMENT_SCORE = 2
CONSTRUCTIVE_EXTENSION_MAX_10M_PRICE_CHANGE_PCT = 6.0
CONSTRUCTIVE_EXTENSION_PARTICIPATION_REARM_LEVEL = 40.0
CONSTRUCTIVE_EXTENSION_MIN_VOLUME_ACCELERATION = 1.0
CONSTRUCTIVE_EXTENSION_MIN_DOLLAR_FLOW_ACCELERATION = 1.25
_CONSTRUCTIVE_EXTENSION_OWNER = "_gs453_constructive_extension"


def _constructive_extension_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _constructive_extension_aligned(record: dict, timeframe: str) -> bool:
    details = record.get("timeframe_alignment") or {}
    item = details.get(timeframe) if isinstance(details, dict) else None
    return bool(item.get("aligned")) if isinstance(item, dict) else False


def constructive_extension_evidence(record: dict) -> dict:
    """Return GS453 display-only evidence for bounded constructive extension."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _constructive_extension_number(record, "vwap_distance_pct")
    bounded = bool(
        relation == "above"
        and distance is not None
        and CONSTRUCTIVE_EXTENSION_MIN_VWAP_DISTANCE_PCT
        < distance
        <= CONSTRUCTIVE_EXTENSION_MAX_VWAP_DISTANCE_PCT
    )

    score = int(
        _constructive_extension_number(
            record,
            "alignment_score",
            default=0.0,
        )
        or 0.0
    )
    thirty_aligned = _constructive_extension_aligned(record, "30s")
    one_aligned = _constructive_extension_aligned(record, "1m")
    three_aligned = _constructive_extension_aligned(record, "3m")
    ladder_constructive = bool(
        score >= CONSTRUCTIVE_EXTENSION_MIN_ALIGNMENT_SCORE
        and thirty_aligned
        and one_aligned
    )

    change_10m = abs(
        _constructive_extension_number(
            record,
            "price_change_10m_pct",
            default=999.0,
        )
        or 999.0
    )
    nonvertical = (
        change_10m <= CONSTRUCTIVE_EXTENSION_MAX_10M_PRICE_CHANGE_PCT
    )

    participation = (
        _constructive_extension_number(
            record,
            "participation_surge_score",
            "participation_score",
            default=0.0,
        )
        or 0.0
    )
    volume_accel = (
        _constructive_extension_number(
            record,
            "volume_acceleration",
            default=0.0,
        )
        or 0.0
    )
    dollar_flow = (
        _constructive_extension_number(
            record,
            "dollar_flow_acceleration",
            "dollar_flow_acceleration_1m",
            default=0.0,
        )
        or 0.0
    )
    fresh_flow = bool(
        volume_accel >= CONSTRUCTIVE_EXTENSION_MIN_VOLUME_ACCELERATION
        or dollar_flow
        >= CONSTRUCTIVE_EXTENSION_MIN_DOLLAR_FLOW_ACCELERATION
    )
    participation_ready = (
        participation >= CONSTRUCTIVE_EXTENSION_PARTICIPATION_REARM_LEVEL
    )

    halted = bool(
        record.get("halted")
        or record.get("is_halted")
        or record.get("suspended")
        or record.get("is_suspended")
    )
    qualifies = bool(
        bounded and ladder_constructive and nonvertical and not halted
    )
    return {
        "qualifies": qualifies,
        "display_only": True,
        "entry_chase_guard_still_authoritative": True,
        "vwap_distance_pct": distance,
        "bounded_extension": bounded,
        "alignment_score": score,
        "thirty_second_aligned": thirty_aligned,
        "one_minute_aligned": one_aligned,
        "three_minute_aligned": three_aligned,
        "ladder_constructive": ladder_constructive,
        "price_change_10m_pct": change_10m,
        "nonvertical": nonvertical,
        "participation_score": participation,
        "participation_ready": participation_ready,
        "volume_acceleration": volume_accel,
        "dollar_flow_acceleration": dollar_flow,
        "fresh_flow": fresh_flow,
    }


def state_with_constructive_extension(original, record: dict) -> dict:
    """Apply the established GS453 DEVELOPING presentation correction."""
    from mide import gs310_unified_opportunity_state as unified

    base = original(record)
    if base.get("state") != unified.CHASE_WAIT:
        return base

    evidence = constructive_extension_evidence(record)
    if not evidence["qualifies"]:
        return base

    view = deepcopy(base)
    view["state"] = unified.DEVELOPING
    view["color"] = unified.STATE_COLORS[unified.DEVELOPING]

    if not evidence["fresh_flow"] or not evidence["participation_ready"]:
        reason = (
            "Bounded VWAP extension with constructive 30s → 1m structure; "
            "momentum has not re-armed yet."
        )
        next_step = (
            "Wait for fresh participation/volume and 3m confirmation. Do not chase; "
            "the underlying entry guard remains authoritative."
        )
    elif not evidence["three_minute_aligned"]:
        reason = (
            "Fresh flow is improving inside a bounded extension, but 3m confirmation "
            "is still developing."
        )
        next_step = (
            "Watch for 3m confirmation while 30s and 1m stay constructive. This is "
            "still observation, not entry permission."
        )
    else:
        reason = (
            "Multi-timeframe structure remains constructive inside a bounded VWAP "
            "extension."
        )
        next_step = (
            "Continue monitoring for an existing re-arm/entry path; do not treat the "
            "DEVELOPING label as permission to chase."
        )

    view["reason"] = reason
    view["next_step"] = next_step
    view["constructive_extension"] = evidence
    return view


def install_constructive_extension_presentation() -> None:
    """Install GS453 display semantics after existing LOOK NOW/retest state semantics."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _CONSTRUCTIVE_EXTENSION_OWNER, False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            return state_with_constructive_extension(original, record)

        _inherit_audio_wrapper(calibrated, current)
        calibrated._gs453_constructive_extension = True
        calibrated._gs453_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


# ---------------------------------------------------------------------------
# GS480 catalyst-story presentation facts
# ---------------------------------------------------------------------------

_CATALYST_STORY_OWNER = "_walter_gs480_story_why_owner"


def catalyst_story_display_facts(record: dict) -> list[str]:
    """Render bounded story facts from authoritative news evidence only."""
    context = record.get("catalyst_story") or {}
    categories = list(context.get("categories") or [])
    quantities = list(context.get("quantities") or [])
    facts: list[str] = []
    if categories:
        readable = [category.replace("_", " ").title() for category in categories[:3]]
        facts.append("Story: " + " · ".join(readable))
    role_facts: list[str] = []
    for item in quantities:
        role = str(item.get("role") or "")
        if role in {
            "DEAL_OR_BACKLOG",
            "REVENUE",
            "INVESTMENT_OR_FUNDING",
            "DILUTION_OR_FINANCING",
        }:
            role_facts.append(
                f"{item.get('text')} {role.replace('_', ' ').lower()}"
            )
        if len(role_facts) >= 3:
            break
    if role_facts:
        facts.append(" · ".join(role_facts))
    return facts


def install_catalyst_story_presentation() -> None:
    """Install GS480 story facts inside Presentation + Audio ownership."""
    from mide import ui

    current = ui._why_sections
    if getattr(current, _CATALYST_STORY_OWNER, False):
        return

    @wraps(current)
    def why_sections(record):
        sections = dict(current(record))
        facts = catalyst_story_display_facts(record)
        if facts:
            existing = str(sections.get("Catalyst") or "").strip()
            addition = " · ".join(facts)
            if addition not in existing:
                sections["Catalyst"] = (
                    f"{existing} · {addition}" if existing else addition
                )
        return sections

    _inherit_audio_wrapper(why_sections, current)
    setattr(why_sections, _CATALYST_STORY_OWNER, True)
    why_sections._gs480_original = current
    ui._why_sections = why_sections


# ---------------------------------------------------------------------------
# GS503 catalyst/company-scale operator presentation
# ---------------------------------------------------------------------------

_CATALYST_SCALE_WHY_OWNER = "_walter_gs503_scale_why_owner"


def catalyst_company_scale_display_summary(record: dict) -> str:
    """Return the bounded factual company-scale summary for operator display."""
    detail = record.get("catalyst_company_scale") or {}
    return str(detail.get("summary") or "").strip()


def install_catalyst_company_scale_presentation() -> None:
    """Append GS503 relative-scale facts to the Catalyst presentation section."""
    from mide import ui

    current = ui._why_sections
    if getattr(current, _CATALYST_SCALE_WHY_OWNER, False):
        return

    @wraps(current)
    def why_sections_with_company_scale(record):
        sections = dict(current(record))
        summary = catalyst_company_scale_display_summary(record)
        if summary:
            existing = str(sections.get("Catalyst") or "").strip()
            if summary not in existing:
                sections["Catalyst"] = (
                    f"{existing} · {summary}" if existing else summary
                )
        return sections

    _inherit_audio_wrapper(why_sections_with_company_scale, current)
    setattr(
        why_sections_with_company_scale,
        _CATALYST_SCALE_WHY_OWNER,
        True,
    )
    why_sections_with_company_scale._gs503_catalyst_company_scale = True
    why_sections_with_company_scale._gs503_original = current
    ui._why_sections = why_sections_with_company_scale


# ---------------------------------------------------------------------------
# GS511 Entry Window VWAP presentation truth
# ---------------------------------------------------------------------------

ENTRY_WINDOW_NEAR_VWAP_MAX_PCT = 2.0
_ENTRY_WINDOW_VWAP_OWNER = "_walter_gs511_entry_window_vwap_truth"


def _entry_window_number(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def entry_window_near_vwap(record: dict) -> bool:
    """Return the established presentation-safe near-VWAP condition."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _entry_window_number(record, "vwap_distance_pct")
    return relation == "above" and (
        distance is None or distance <= ENTRY_WINDOW_NEAR_VWAP_MAX_PCT
    )


def install_entry_window_vwap_truth() -> None:
    """Keep Entry Window display/feed truth inside Walter's established VWAP zone."""
    from mide import escalation
    from mide import live_opportunity_feed

    current_state = escalation.escalation_state
    if getattr(current_state, _ENTRY_WINDOW_VWAP_OWNER, False):
        # Warm Streamlit reruns can retain the feed module's imported snapshot
        # binding even when escalation already owns this presentation correction.
        live_opportunity_feed.escalation_snapshot = escalation.escalation_snapshot
        return

    current_snapshot = escalation.escalation_snapshot

    @wraps(current_state)
    def escalation_state(record: dict) -> str:
        existing = current_state(record)
        if existing != escalation.ENTRY_WINDOW_OPEN:
            return existing
        if entry_window_near_vwap(record):
            return existing

        distance = _entry_window_number(record, "vwap_distance_pct")
        if distance is not None and distance > 5.0:
            return escalation.TOO_EXTENDED

        relation = str(record.get("vwap_relation") or "").strip().lower()
        trend = bool(
            record.get("supertrend_bullish") or record.get("supertrend_flip")
        )
        if relation == "above" and trend:
            return escalation.WATCH_CLOSELY
        return escalation.MONITOR

    @wraps(current_snapshot)
    def escalation_snapshot(record: dict) -> dict:
        snapshot = dict(current_snapshot(record))
        snapshot["state"] = escalation_state(record)
        return snapshot

    setattr(escalation_state, _ENTRY_WINDOW_VWAP_OWNER, True)
    setattr(escalation_snapshot, _ENTRY_WINDOW_VWAP_OWNER, True)
    escalation_state._gs511_original = current_state
    escalation_snapshot._gs511_original = current_snapshot

    escalation.escalation_state = escalation_state
    escalation.escalation_snapshot = escalation_snapshot
    live_opportunity_feed.escalation_snapshot = escalation_snapshot


# ---------------------------------------------------------------------------
# GS504 categorical browser-action audio
# ---------------------------------------------------------------------------

DISTINCT_ATTENTION_OWNER = "_walter_gs504_distinct_attention_alarm"
DISTINCT_ATTENTION_MARKER = "GS504: categorical action audio"


def distinct_attention_markup(markup: str) -> str:
    """Replace only tier-2/3 synthesis after GS367 chooses the semantic tier."""
    text = str(markup or "")
    if DISTINCT_ATTENTION_MARKER in text:
        return text

    helper_needle = "    const emitPattern = (context) => {"
    if helper_needle not in text:
        return text

    helpers = r"""
    // GS504: categorical action audio.
    // Tier 2 is a harmonic two-strike bell; tier 3 is a sustained alternating siren.
    // Tier 1 intentionally falls through to Walter's existing routine heartbeat.
    const gs504AttentionBell = (context, startBase) => {
      const strike = (start, fundamental) => {
        const frequencies = [
          [fundamental, 0.34],
          [fundamental * 1.5, 0.18],
          [fundamental * 2.01, 0.10],
        ];
        frequencies.forEach(([frequency, peak]) => {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(Number(frequency), start);
          gain.gain.setValueAtTime(0.0001, start);
          gain.gain.exponentialRampToValueAtTime(Number(peak), start + 0.018);
          gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.62);
          oscillator.connect(gain);
          gain.connect(context.destination);
          oscillator.start(start);
          oscillator.stop(start + 0.66);
        });
      };
      strike(startBase, 523.25);
      strike(startBase + 0.52, 783.99);
    };

    const gs504UrgentSiren = (context, startBase) => {
      const oscillator = context.createOscillator();
      const harmonic = context.createOscillator();
      const gain = context.createGain();
      const harmonicGain = context.createGain();

      oscillator.type = 'sawtooth';
      harmonic.type = 'sine';
      gain.gain.setValueAtTime(0.0001, startBase);
      harmonicGain.gain.setValueAtTime(0.0001, startBase);
      gain.gain.exponentialRampToValueAtTime(0.30, startBase + 0.025);
      harmonicGain.gain.exponentialRampToValueAtTime(0.12, startBase + 0.025);

      const sweep = [
        [980, 0.00], [1510, 0.16],
        [980, 0.32], [1510, 0.48],
        [980, 0.64], [1510, 0.80],
        [1120, 0.98],
      ];
      sweep.forEach(([frequency, offset], index) => {
        const when = startBase + Number(offset);
        if (index === 0) {
          oscillator.frequency.setValueAtTime(Number(frequency), when);
          harmonic.frequency.setValueAtTime(Number(frequency) * 1.5, when);
        } else {
          oscillator.frequency.linearRampToValueAtTime(Number(frequency), when);
          harmonic.frequency.linearRampToValueAtTime(Number(frequency) * 1.5, when);
        }
      });

      gain.gain.exponentialRampToValueAtTime(0.0001, startBase + 1.08);
      harmonicGain.gain.exponentialRampToValueAtTime(0.0001, startBase + 1.08);
      oscillator.connect(gain);
      harmonic.connect(harmonicGain);
      gain.connect(context.destination);
      harmonicGain.connect(context.destination);
      oscillator.start(startBase);
      harmonic.start(startBase);
      oscillator.stop(startBase + 1.10);
      harmonic.stop(startBase + 1.10);
    };

"""
    text = text.replace(
        helper_needle,
        helpers + helper_needle,
        1,
    )

    branch_needle = (
        "        const startBase = context.currentTime + 0.035;\n"
        "        const pattern = patterns[String(tier)] || patterns['1'];"
    )
    branch_replacement = (
        "        const startBase = context.currentTime + 0.035;\n"
        "        if (tier === 2) {\n"
        "          gs504AttentionBell(context, startBase);\n"
        "          broker.emittedToken = token;\n"
        "          clearPending();\n"
        "          return true;\n"
        "        }\n"
        "        if (tier === 3) {\n"
        "          gs504UrgentSiren(context, startBase);\n"
        "          broker.emittedToken = token;\n"
        "          clearPending();\n"
        "          return true;\n"
        "        }\n"
        "        const pattern = patterns[String(tier)] || patterns['1'];"
    )
    if branch_needle not in text:
        return text
    return text.replace(
        branch_needle,
        branch_replacement,
        1,
    )


def install_distinct_attention_audio() -> None:
    """Install the categorical GS504 browser-synthesis layer."""
    from mide import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(
        current,
        DISTINCT_ATTENTION_OWNER,
        False,
    ):
        return

    @wraps(current)
    def browser_broker_markup(
        scan_token: str,
        tier: int,
    ) -> str:
        return distinct_attention_markup(
            current(scan_token, tier)
        )

    _inherit_audio_wrapper(
        browser_broker_markup,
        current,
    )
    browser_broker_markup._gs504_distinct_attention_alarm = True
    browser_broker_markup._gs504_original = current
    setattr(
        browser_broker_markup,
        DISTINCT_ATTENTION_OWNER,
        True,
    )
    broker.browser_broker_markup = (
        browser_broker_markup
    )


# ---------------------------------------------------------------------------
# GS516 visible browser alert-audio health
# ---------------------------------------------------------------------------

def alert_audio_health_markup() -> str:
    return r"""
    <style>
      .walter-audio-health {
        display:flex; align-items:center; justify-content:space-between; gap:8px;
        border:1px solid #475569; border-radius:8px; padding:7px 8px;
        font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        background:#111827; color:#f8fafc;
      }
      .walter-audio-health.ready { border-color:#22c55e; background:#052e16; }
      .walter-audio-health.warn { border-color:#f59e0b; background:#451a03; }
      .walter-audio-health.bad { border-color:#ef4444; background:#450a0a; }
      .walter-audio-health button {
        border:1px solid #64748b; border-radius:6px; padding:5px 8px;
        background:#172033; color:#f8fafc; cursor:pointer; font-weight:800;
        white-space:nowrap;
      }
      #walter-audio-health-status { font-weight:900; line-height:1.25; }
    </style>
    <div id="walter-audio-health" class="walter-audio-health warn">
      <span id="walter-audio-health-status">AUDIO STATUS CHECKING…</span>
      <button id="walter-audio-health-button" type="button">Re-arm / test</button>
    </div>
    <script>
    (() => {
      const box = document.getElementById('walter-audio-health');
      const status = document.getElementById('walter-audio-health-status');
      const button = document.getElementById('walter-audio-health-button');
      let root = window;
      try { if (window.parent) root = window.parent; } catch (_) { root = window; }

      const brokerKey = '__walterGS367ChimeBroker';
      const ensureBroker = () => {
        let broker = root[brokerKey];
        if (!broker || typeof broker !== 'object') {
          broker = root[brokerKey] = {
            token: null, tier: 0, timer: null, emittedToken: null,
            audioContext: null, pendingToken: null, pendingTier: 0,
            pendingEmit: null, unlockBound: false,
          };
        }
        return broker;
      };
      const readArmed = () => {
        try {
          return Boolean(root.__walterVoiceArmed) ||
            (root.sessionStorage &&
             root.sessionStorage.getItem('walterVoiceArmed') === '1');
        } catch (_) { return false; }
      };
      const markArmed = () => {
        try { root.__walterVoiceArmed = true; } catch (_) {}
        try {
          if (root.sessionStorage) root.sessionStorage.setItem('walterVoiceArmed', '1');
        } catch (_) {}
      };
      const audioReady = () => {
        try {
          const broker = ensureBroker();
          return Boolean(broker.audioContext && broker.audioContext.state === 'running');
        } catch (_) { return false; }
      };
      const paint = (kind, text) => {
        if (!box || !status) return;
        box.className = 'walter-audio-health ' + kind;
        status.textContent = text;
      };
      const refresh = () => {
        if (audioReady()) {
          paint('ready', 'AUDIO READY');
        } else if (readArmed()) {
          paint('bad', 'AUDIO DISARMED AFTER RELOAD · RE-ARM');
        } else {
          paint('warn', 'AUDIO NOT ARMED · RE-ARM');
        }
      };

      const testVoice = () => {
        try {
          const synth = root.speechSynthesis || window.speechSynthesis;
          const Utterance =
            root.SpeechSynthesisUtterance || window.SpeechSynthesisUtterance;
          if (!synth || !Utterance) return;
          const utterance = new Utterance('Walter alerts ready.');
          utterance.rate = 0.95;
          utterance.pitch = 0.9;
          utterance.volume = 1.0;
          synth.speak(utterance);
        } catch (_) {}
      };

      const rearm = () => {
        try {
          const AudioContextCtor =
            root.AudioContext || root.webkitAudioContext ||
            window.AudioContext || window.webkitAudioContext;
          if (!AudioContextCtor) {
            paint('bad', 'WEB AUDIO UNAVAILABLE');
            return;
          }
          const broker = ensureBroker();
          let ctx = broker.audioContext;
          if (!ctx || ctx.state === 'closed') {
            ctx = new AudioContextCtor();
            broker.audioContext = ctx;
          }
          const play = () => {
            if (!ctx || ctx.state !== 'running') {
              paint('bad', 'AUDIO BLOCKED · CLICK AGAIN');
              return;
            }
            // GS524: the health control must prove an *audible* path, not merely
            // a running AudioContext. Use a short two-strike bell at a practical
            // level, in the same parent-window context used by GS367/GS504.
            const strike = (start, frequency) => {
              const osc = ctx.createOscillator();
              const overtone = ctx.createOscillator();
              const gain = ctx.createGain();
              const overtoneGain = ctx.createGain();
              osc.type = 'sine';
              overtone.type = 'sine';
              osc.frequency.setValueAtTime(frequency, start);
              overtone.frequency.setValueAtTime(frequency * 1.5, start);
              gain.gain.setValueAtTime(0.0001, start);
              overtoneGain.gain.setValueAtTime(0.0001, start);
              gain.gain.exponentialRampToValueAtTime(0.30, start + 0.015);
              overtoneGain.gain.exponentialRampToValueAtTime(0.12, start + 0.015);
              gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.45);
              overtoneGain.gain.exponentialRampToValueAtTime(0.0001, start + 0.45);
              osc.connect(gain); gain.connect(ctx.destination);
              overtone.connect(overtoneGain); overtoneGain.connect(ctx.destination);
              osc.start(start); overtone.start(start);
              osc.stop(start + 0.48); overtone.stop(start + 0.48);
            };
            const base = ctx.currentTime + 0.03;
            strike(base, 523.25);
            strike(base + 0.42, 783.99);
            markArmed();
            testVoice();
            paint('ready', 'AUDIO READY · TEST PLAYING');
            window.setTimeout(() => {
              if (audioReady()) paint('ready', 'AUDIO READY');
            }, 1800);
          };
          if (ctx.state === 'running') {
            play();
          } else if (ctx.resume) {
            const resumed = ctx.resume();
            if (resumed && resumed.then) {
              resumed.then(play).catch(() =>
                paint('bad', 'AUDIO BLOCKED · CLICK AGAIN'));
            } else {
              play();
            }
          } else {
            paint('bad', 'AUDIO BLOCKED · CLICK AGAIN');
          }
        } catch (_) {
          paint('bad', 'AUDIO TEST FAILED');
        }
      };

      if (button) button.addEventListener('click', rearm);
      refresh();
      const timer = window.setInterval(refresh, 1000);
      window.addEventListener('beforeunload', () => window.clearInterval(timer));
    })();
    </script>
    """


def render_sidebar_audio_health(st_module) -> None:
    """Render transport health at the sidebar control boundary, never in mission slots."""
    try:
        st_module.components.v1.html(
            alert_audio_health_markup(),
            height=58,
            scrolling=False,
        )
    except Exception:
        # Browser transport controls must never interfere with the Radar itself.
        pass


# ---------------------------------------------------------------------------
# GS414/GS436 final enriched Opportunity render boundary
# ---------------------------------------------------------------------------

FINAL_ORDER_OWNER_ATTR = "_walter_final_enriched_opportunity_order_owner"


def final_enriched_opportunity_records(
    records: list[dict],
    *,
    actionable_function=None,
) -> list[dict]:
    """Build the complete enriched presentation collection, then sort it once."""
    from mide import ui
    from mide.gs369_escalation_priority_order import ordered_escalation_records
    from mide.gs477_leader_reset_reignition import enrich_visible_records

    actionable = actionable_function or ui.actionable_candidate_records
    enriched = enrich_visible_records(list(records or []), actionable)
    return ordered_escalation_records(enriched)


def bind_final_enriched_opportunity_order(
    attr: str,
    *,
    show_legend: bool = False,
) -> None:
    """Freeze final enrichment/order across one public Opportunity renderer."""
    from mide import ui

    current = getattr(ui, attr)
    if getattr(current, FINAL_ORDER_OWNER_ATTR, False):
        return

    def render_with_final_enriched_order(records: list[dict]) -> None:
        public_actionable = ui.actionable_candidate_records
        ordered = final_enriched_opportunity_records(
            records,
            actionable_function=public_actionable,
        )

        def frozen_actionable(_records: list[dict]) -> list[dict]:
            return list(ordered)

        _inherit_audio_wrapper(frozen_actionable, public_actionable)
        ui.actionable_candidate_records = frozen_actionable
        try:
            if show_legend:
                ui.st.caption(
                    "Order: P/E Strength (Participation + Expansion) descending. "
                    "Color = structural state, not score."
                )
            return current(list(ordered))
        finally:
            ui.actionable_candidate_records = public_actionable

    _inherit_audio_wrapper(render_with_final_enriched_order, current)
    render_with_final_enriched_order._gs414_final_enriched_opportunity_order = True
    render_with_final_enriched_order._gs436_final_render_hard_bind = True
    render_with_final_enriched_order._gs539_live_path_hard_bind = True
    render_with_final_enriched_order._gs414_original = current
    setattr(render_with_final_enriched_order, FINAL_ORDER_OWNER_ATTR, True)
    setattr(ui, attr, render_with_final_enriched_order)


__all__ = [
    "progression_change",
    "spoken_progression_rung",
    "progression_audio_phrase",
    "install_progression_alert_priority",
    "install_explosive_30s_presentation",
    "install_explosive_30s_audio",
    "install_explosive_30s_order",
    "install_explosive_30s_state",
    "explosive_30s_audio_phrase",
    "ordered_explosive_30s_records",
    "explosive_30s_attention_band",
    "state_with_explosive_30s",
    "explosive_30s_surge",
    "explosive_30s_number",
    "alert_audio_health_markup",
    "render_sidebar_audio_health",
    "install_distinct_attention_audio",
    "distinct_attention_markup",
    "DISTINCT_ATTENTION_OWNER",
    "DISTINCT_ATTENTION_MARKER",
    "install_operator_attention_audio",
    "operator_attention_audio_phrase",
    "operator_attention_candidate",
    "legacy_operator_attention_gate_passed",
    "install_preflip_presentation",
    "install_preflip_order",
    "install_preflip_state",
    "ordered_preflip_records",
    "effective_preflip_attention_band",
    "state_with_preflip",
    "preflip_tf_phrase",
    "preflip_ignition_watch",
    "preflip_timeframe_detail",
    "preflip_gap_pct",
    "preflip_number",
    "install_cascade_runway_presentation",
    "install_cascade_runway_alerts",
    "install_cascade_runway_state",
    "cascade_runway_alert",
    "state_with_cascade_runway",
    "cascade_runway_text",
    "install_st_flip_compression_presentation",
    "install_st_flip_compression_alerts",
    "install_st_flip_compression_state",
    "st_flip_compression_phrase",
    "st_flip_spoken",
    "st_flip_compression_change",
    "state_with_st_flip_compression",
    "ST_FLIP_ANTI_CHASE_DISTANCE_PCT",
    "install_price_trajectory_presentation",
    "ordered_trajectory_records",
    "effective_trajectory_attention_band",
    "trajectory_attention",
    "PRICE_TRAJECTORY_BAND",
    "install_constructive_extension_presentation",
    "state_with_constructive_extension",
    "constructive_extension_evidence",
    "CONSTRUCTIVE_EXTENSION_MIN_VWAP_DISTANCE_PCT",
    "CONSTRUCTIVE_EXTENSION_MAX_VWAP_DISTANCE_PCT",
    "bind_final_enriched_opportunity_order",
    "final_enriched_opportunity_records",
    "FINAL_ORDER_OWNER_ATTR",
    "install_entry_window_vwap_truth",
    "entry_window_near_vwap",
    "ENTRY_WINDOW_NEAR_VWAP_MAX_PCT",
    "install_catalyst_company_scale_presentation",
    "catalyst_company_scale_display_summary",
    "install_catalyst_story_presentation",
    "catalyst_story_display_facts",
    "actionable_candidate_records",
    "install_market_event_presentation",
    "market_event_markup",
    "visible_market_events",
    "_LATEST_ACTIONABLE_SYMBOLS",
    "install_market_leader_continuity",
    "market_leader_markup",
    "market_leader_candidate",
    "LEADER_DOMINANCE",
    "MIN_DOLLAR_VOLUME",
    "MAJOR_MOVER_PCT",
    "reset_extreme_banner_decay_state",
    "install_extreme_banner_decay",
    "prioritized_extreme_with_decay",
    "EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS",
    "install_base_extreme_presentation",
    "extreme_event_markup",
    "prioritized_extreme_event",
    "base_extreme_market_event",
    "EXTREME_MOVER_PCT",
    "install_extreme_awareness_continuity",
    "extreme_awareness_continuity",
    "install_extreme_selection_continuity",
    "prioritized_extreme_with_watch_continuity",
    "activate_extreme_event_stage",
    "truthful_extreme_market_event",
    "cleaned_extreme_event",
    "ANTI_CHASE_VWAP_DISTANCE_PCT",
    "install_pe_strength_order",
    "install_pe_strength_state",
    "state_with_pe_strength",
    "activate_operator_order_stage",
    "ordered_pe_strength_records",
    "pe_strength_score",
    "expansion_value",
    "participation_value",
    "ordered_fresh_event_records",
    "fresh_maturation_event",
    "ordered_rank_aware_records",
    "current_mission_rank",
    "ordered_state_contiguous_records",
    "attention_tiebreak",
    "strict_state_band",
    "ordered_state_first_records",
    "effective_operator_attention_band",
    "install_audio_architecture_gate_bridge",
    "install_maturation_transition_audio",
    "maturation_audio_phrase",
    "maturation_transition",
    "authoritative_gate_passed",
    "FRESH_3M_SECONDS",
    "augment_leader_reset_records",
    "data_integrity_markup",
    "decision_funnel_markup",
    "enrich_visible_records",
    "inject_css",
    "install_leader_reset_audio",
    "leader_reset_audio_phrase",
    "market_session_quality_markup",
    "mission_control_header_markup",
    "opportunity_card",
    "play_alert",
    "radar_table",
    "rejected_candidates_table",
    "rejection_diagnostics",
    "render_calibration_dashboard",
    "render_early_setups",
    "render_escalation_engine",
    "render_live_evidence_diagnostics",
    "render_live_opportunity_feed",
    "render_sidebar_audio_health",
    "render_walter_mission_control",
    "scanner_v2_dashboard_counts",
    "scanner_v2_display_sections",
]
