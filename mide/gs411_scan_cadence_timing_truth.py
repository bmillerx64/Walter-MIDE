"""GS411: persist exact scan-cadence timing truth without changing behavior.

Live September 9 validation showed completed Flight Recorder rows arriving roughly
75-80 seconds apart even after GS405/GS409 targeted a 60-second start-to-start
cadence. Existing ``pipeline_timing_summary`` measures work inside the scan, but the
Flight Recorder does not preserve the lifecycle timestamps needed to separate scan
runtime from scheduler/rerun delay.

GS411 is observation only. It records the existing scheduler due boundary, rerun
suppression decisions, scan-attempt timestamp, watchdog acquisition, prior scan
finish, and Flight Recorder persistence boundary. It does not schedule a scan,
change a deadline, alter the watchdog, or mutate trading records/decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any


DUE_EVENT_KEY = "_walter_gs411_due_event"
CURRENT_SCAN_KEY = "_walter_gs411_current_scan"
LAST_ATTEMPT_EPOCH_KEY = "_walter_gs411_last_attempt_epoch"
LAST_FINISHED_EPOCH_KEY = "_walter_gs411_last_finished_epoch"
RERUN_DECISIONS_KEY = "_walter_gs411_rerun_decisions"
MAX_RERUN_DECISIONS = 20


def _now_epoch() -> float:
    return time.time()


def _epoch(value: Any) -> float | None:
    if isinstance(value, datetime):
        try:
            return float(value.timestamp())
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    try:
        return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()
    except (OverflowError, OSError, TypeError, ValueError):
        return None


def _ms(later: float | None, earlier: float | None) -> float | None:
    if later is None or earlier is None:
        return None
    return round((float(later) - float(earlier)) * 1000.0, 3)


def _get_session_state():
    """Return Streamlit session state when a live ScriptRunContext exists."""
    try:
        import streamlit as st

        state = st.session_state
        state.get(DUE_EVENT_KEY)
        return state
    except Exception:
        return None


def _gs409_wrapper_active() -> bool:
    try:
        import streamlit as st

        return bool(getattr(st.rerun, "_gs409_due_autoscan_cadence", False))
    except Exception:
        return False


def _same_attempt(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and abs(left - right) < 0.001


def record_due_observation(
    state,
    *,
    refresh_seconds: int,
    last_updated: datetime | None,
    last_scan_attempt: datetime | None,
    retry_seconds: int,
    observed_epoch: float | None = None,
) -> dict[str, Any]:
    """Record the first/last true autoscan-due observation for one prior attempt."""
    observed = _now_epoch() if observed_epoch is None else float(observed_epoch)
    prior_attempt = _epoch(last_scan_attempt)
    updated = _epoch(last_updated)
    retry_pending = bool(
        last_scan_attempt
        and (last_updated is None or last_scan_attempt > last_updated)
    )
    threshold = max(1, int(retry_seconds if retry_pending else refresh_seconds))
    scheduled_due = prior_attempt + threshold if prior_attempt is not None else None

    existing = state.get(DUE_EVENT_KEY)
    if isinstance(existing, dict) and _same_attempt(
        _epoch(existing.get("prior_attempt_epoch")), prior_attempt
    ):
        event = dict(existing)
        event["last_observed_epoch"] = observed
        event["due_true_count"] = int(event.get("due_true_count", 1) or 1) + 1
    else:
        event = {
            "prior_attempt_epoch": prior_attempt,
            "last_updated_epoch": updated,
            "scheduled_due_epoch": scheduled_due,
            "first_observed_epoch": observed,
            "last_observed_epoch": observed,
            "due_true_count": 1,
            "refresh_seconds": max(1, int(refresh_seconds)),
            "retry_seconds": max(1, int(retry_seconds)),
            "cadence_mode": "retry" if retry_pending else "refresh",
        }
    state[DUE_EVENT_KEY] = event
    return event


def record_rerun_decision(
    state,
    *,
    reason: str | None,
    protect_post_scan: bool,
    process_scan_running: bool | None,
    observed_epoch: float | None = None,
) -> dict[str, Any]:
    """Append one GS409 rerun decision without changing the decision itself."""
    observed = _now_epoch() if observed_epoch is None else float(observed_epoch)
    event = {
        "observed_epoch": observed,
        "reason": reason,
        "allowed": reason is None,
        "protect_post_scan": bool(protect_post_scan),
        "process_scan_running": process_scan_running,
    }
    history = list(state.get(RERUN_DECISIONS_KEY) or [])
    history.append(event)
    state[RERUN_DECISIONS_KEY] = history[-MAX_RERUN_DECISIONS:]
    return event


def _due_event_matches_previous_attempt(
    due_event: dict[str, Any] | None,
    previous_attempt_epoch: float | None,
    current_attempt_epoch: float | None,
) -> bool:
    if not isinstance(due_event, dict):
        return False
    due_prior = _epoch(due_event.get("prior_attempt_epoch"))
    if _same_attempt(due_prior, previous_attempt_epoch):
        return True
    # First-cycle/recovery fallback: accept a recent due observation only when it
    # occurred before this attempt. This avoids reusing stale due truth.
    observed = _epoch(due_event.get("last_observed_epoch"))
    if observed is None or current_attempt_epoch is None:
        return False
    age = current_attempt_epoch - observed
    return 0.0 <= age <= 300.0


def capture_scan_acquired(state, *, acquired_epoch: float | None = None) -> dict[str, Any]:
    """Capture the watchdog-acquisition boundary for the scan about to run."""
    acquired = _now_epoch() if acquired_epoch is None else float(acquired_epoch)
    current_attempt = _epoch(state.get("last_scan_attempt"))
    previous_attempt = _epoch(state.get(LAST_ATTEMPT_EPOCH_KEY))
    previous_finished = _epoch(state.get(LAST_FINISHED_EPOCH_KEY))
    manual_request = _epoch(state.get("_walter_scan_requested_epoch"))
    due_event = state.pop(DUE_EVENT_KEY, None)
    matched_due = (
        dict(due_event)
        if _due_event_matches_previous_attempt(
            due_event if isinstance(due_event, dict) else None,
            previous_attempt,
            current_attempt,
        )
        else None
    )

    if manual_request is not None:
        trigger = "manual"
        matched_due = None
    elif matched_due is not None:
        trigger = "autoscan_fragment"
    else:
        trigger = "fallback_or_initial"

    rerun_decisions = [
        dict(item)
        for item in list(state.pop(RERUN_DECISIONS_KEY, []) or [])
        if isinstance(item, dict)
    ]
    event = {
        "trigger": trigger,
        "previous_attempt_epoch": previous_attempt,
        "previous_finished_epoch": previous_finished,
        "attempt_epoch": current_attempt,
        "acquired_epoch": acquired,
        "manual_request_epoch": manual_request,
        "due_event": matched_due,
        "rerun_decisions": rerun_decisions,
        "gs409_wrapper_active": _gs409_wrapper_active(),
    }
    state[CURRENT_SCAN_KEY] = event
    if current_attempt is not None:
        state[LAST_ATTEMPT_EPOCH_KEY] = current_attempt
    return event


def capture_scan_finished(state, *, finished_epoch: float | None = None) -> float:
    """Persist the watchdog release time for the next scan's cadence geometry."""
    finished = _now_epoch() if finished_epoch is None else float(finished_epoch)
    state[LAST_FINISHED_EPOCH_KEY] = finished
    return finished


def build_scan_timing_truth(
    state,
    *,
    recorder_epoch: float | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe timing snapshot for the Flight Recorder persistence boundary."""
    recorder = _now_epoch() if recorder_epoch is None else float(recorder_epoch)
    event = dict(state.get(CURRENT_SCAN_KEY) or {}) if state is not None else {}
    due = dict(event.get("due_event") or {})

    previous_attempt = _epoch(event.get("previous_attempt_epoch"))
    previous_finished = _epoch(event.get("previous_finished_epoch"))
    attempt = _epoch(event.get("attempt_epoch"))
    acquired = _epoch(event.get("acquired_epoch"))
    manual_request = _epoch(event.get("manual_request_epoch"))
    scheduled_due = _epoch(due.get("scheduled_due_epoch"))
    first_due = _epoch(due.get("first_observed_epoch"))
    last_due = _epoch(due.get("last_observed_epoch"))

    decisions = []
    for raw in event.get("rerun_decisions") or []:
        if not isinstance(raw, dict):
            continue
        observed = _epoch(raw.get("observed_epoch"))
        decisions.append(
            {
                "observed_at": _iso(observed),
                "reason": raw.get("reason"),
                "allowed": bool(raw.get("allowed")),
                "protect_post_scan": bool(raw.get("protect_post_scan")),
                "process_scan_running": raw.get("process_scan_running"),
            }
        )

    return {
        "authority": "OBSERVATIONAL_ONLY",
        "boundary": "flight_recorder_persistence",
        "trigger": event.get("trigger", "unknown"),
        "previous_scan_attempt_at": _iso(previous_attempt),
        "previous_scan_finished_at": _iso(previous_finished),
        "scheduled_due_at": _iso(scheduled_due),
        "scheduler_due_first_observed_at": _iso(first_due),
        "scheduler_due_last_observed_at": _iso(last_due),
        "scheduler_due_true_count": int(due.get("due_true_count", 0) or 0),
        "manual_request_at": _iso(manual_request),
        "attempted_at": _iso(attempt),
        "watchdog_acquired_at": _iso(acquired),
        "recorder_at": _iso(recorder),
        "configured_refresh_seconds": due.get("refresh_seconds"),
        "retry_seconds": due.get("retry_seconds"),
        "cadence_mode": due.get("cadence_mode"),
        "previous_start_to_current_attempt_ms": _ms(attempt, previous_attempt),
        "previous_finish_to_current_attempt_ms": _ms(attempt, previous_finished),
        "scheduled_due_to_first_observed_ms": _ms(first_due, scheduled_due),
        "first_due_observed_to_attempt_ms": _ms(attempt, first_due),
        "last_due_observed_to_attempt_ms": _ms(attempt, last_due),
        "manual_request_to_attempt_ms": _ms(attempt, manual_request),
        "attempt_to_watchdog_acquire_ms": _ms(acquired, attempt),
        "watchdog_acquire_to_recorder_ms": _ms(recorder, acquired),
        "attempt_to_recorder_ms": _ms(recorder, attempt),
        "rerun_decisions": decisions,
        "last_rerun_decision": decisions[-1] if decisions else None,
        "gs409_wrapper_active": bool(event.get("gs409_wrapper_active", False)),
    }


def attach_scan_timing_truth(
    scan: dict,
    state,
    *,
    recorder_epoch: float | None = None,
) -> dict:
    """Copy a scan and attach lifecycle timing without mutating the source scan."""
    enriched = dict(scan)
    enriched["scan_timing_truth"] = build_scan_timing_truth(
        state, recorder_epoch=recorder_epoch
    )
    return enriched


def _inherit_gs_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install observational hooks after GS408 at the safe GS410 late boundary."""
    from . import flight_recorder, gs351_session_rerun_isolation as reruns
    from . import session_controls

    current_due = session_controls.autoscan_request_due
    if not getattr(current_due, "_gs411_scan_cadence_timing_truth", False):
        def due_with_observation(
            refresh_seconds: int,
            last_updated: datetime | None,
            last_scan_attempt: datetime | None,
            *,
            retry_seconds: int = 5,
            now: datetime | None = None,
        ) -> bool:
            due = current_due(
                refresh_seconds,
                last_updated,
                last_scan_attempt,
                retry_seconds=retry_seconds,
                now=now,
            )
            if due:
                state = _get_session_state()
                if state is not None:
                    record_due_observation(
                        state,
                        refresh_seconds=refresh_seconds,
                        last_updated=last_updated,
                        last_scan_attempt=last_scan_attempt,
                        retry_seconds=retry_seconds,
                        observed_epoch=_epoch(now) if now is not None else _now_epoch(),
                    )
            return due

        _inherit_gs_markers(due_with_observation, current_due)
        due_with_observation._gs411_scan_cadence_timing_truth = True
        due_with_observation._gs411_original = current_due
        session_controls.autoscan_request_due = due_with_observation

    current_begin = session_controls.begin_scheduled_scan
    if not getattr(current_begin, "_gs411_scan_cadence_timing_truth", False):
        def begin_with_observation(state):
            capture_scan_acquired(state)
            return current_begin(state)

        _inherit_gs_markers(begin_with_observation, current_begin)
        begin_with_observation._gs411_scan_cadence_timing_truth = True
        begin_with_observation._gs411_original = current_begin
        session_controls.begin_scheduled_scan = begin_with_observation

    current_finish = session_controls.finish_scan
    if not getattr(current_finish, "_gs411_scan_cadence_timing_truth", False):
        def finish_with_observation(state):
            result = current_finish(state)
            # GS409's wrapper records its own finish epoch. Reuse that exact value
            # when available so the two diagnostic layers share one boundary.
            finished = _epoch(state.get(reruns.LAST_SCAN_FINISHED_KEY))
            capture_scan_finished(
                state,
                finished_epoch=finished if finished is not None else _now_epoch(),
            )
            return result

        _inherit_gs_markers(finish_with_observation, current_finish)
        finish_with_observation._gs411_scan_cadence_timing_truth = True
        finish_with_observation._gs411_original = current_finish
        session_controls.finish_scan = finish_with_observation

    current_reason = reruns.rerun_suppression_reason
    if not getattr(current_reason, "_gs411_scan_cadence_timing_truth", False):
        def reason_with_observation(
            state,
            *,
            now: float | None = None,
            epoch_now: float | None = None,
            protect_post_scan: bool = False,
            process_scan_running: bool | None = None,
        ) -> str | None:
            reason = current_reason(
                state,
                now=now,
                epoch_now=epoch_now,
                protect_post_scan=protect_post_scan,
                process_scan_running=process_scan_running,
            )
            record_rerun_decision(
                state,
                reason=reason,
                protect_post_scan=protect_post_scan,
                process_scan_running=process_scan_running,
                observed_epoch=epoch_now if epoch_now is not None else _now_epoch(),
            )
            return reason

        _inherit_gs_markers(reason_with_observation, current_reason)
        reason_with_observation._gs411_scan_cadence_timing_truth = True
        reason_with_observation._gs411_original = current_reason
        reruns.rerun_suppression_reason = reason_with_observation

    current_persist = flight_recorder.persist_replayable_scan
    if not getattr(current_persist, "_gs411_scan_cadence_timing_truth", False):
        def persist_with_timing(recorder, scan: dict, records, *, data_mode=None):
            state = _get_session_state()
            enriched = attach_scan_timing_truth(
                scan,
                state,
                recorder_epoch=_now_epoch(),
            )
            return current_persist(
                recorder,
                enriched,
                records,
                data_mode=data_mode,
            )

        _inherit_gs_markers(persist_with_timing, current_persist)
        persist_with_timing._gs411_scan_cadence_timing_truth = True
        persist_with_timing._gs411_original = current_persist
        flight_recorder.persist_replayable_scan = persist_with_timing
