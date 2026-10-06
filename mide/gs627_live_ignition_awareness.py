"""GS627: process-owned Live Ignition Watch (awareness only).

This lane watches already-completed/cached evidence between Walter's canonical
60-second scans. It never discovers symbols, requests market data, calls scanner
logic, changes state/readiness, speaks, or executes orders.

Inputs:
- last successfully completed process scan (immutable copy);
- process-owned Live Webull provider cache;
- genuine completed Webull 30s bars / GS396 tripwire.

The purpose is operator timing: surface boxes checking in near the 30-second
evidence boundary while the canonical scan remains the sole trading authority.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import datetime, timezone
import threading
from typing import Any

AUTHORITY = "AWARENESS_ONLY_LIVE_IGNITION_WATCH"
_RUNTIME_KEY = "_walter_gs627_live_ignition_awareness"
_RUNTIME_SCHEMA = 1
POLL_SECONDS = 2.0
MAX_RECORDS = 20
MAX_VISIBLE = 8
MIN_BOXES_VISIBLE = 3

# GS640: presentation-only live-regime semantics. These thresholds do not alter
# scanner qualification or Entry authority; they classify already-visible GS627
# observations using cached evidence only.
LIVE_BREAKOUT_MIN_BOXES = 4
LIVE_BREAKOUT_FLOW_MIN = 1.5
LIVE_EXTENDED_VWAP_PCT = 2.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _new_runtime() -> dict[str, Any]:
    return {
        "schema": _RUNTIME_SCHEMA,
        "lock": threading.RLock(),
        "stop": threading.Event(),
        "thread": None,
        "status": "cold",
        "last_evaluated_at": None,
        "last_error_type": None,
        "cycles": 0,
        "observations": [],
        "signatures": {},
        "first_seen": {},
        "changed_at": {},
        "scan_completed_at": None,
    }


def _runtime() -> dict[str, Any]:
    runtime = builtins.__dict__.get(_RUNTIME_KEY)
    if isinstance(runtime, dict) and runtime.get("schema") == _RUNTIME_SCHEMA:
        return runtime
    runtime = _new_runtime()
    builtins.__dict__[_RUNTIME_KEY] = runtime
    return runtime


def snapshot() -> dict:
    runtime = _runtime()
    with runtime["lock"]:
        thread = runtime.get("thread")
        return {
            "authority": AUTHORITY,
            "status": runtime.get("status"),
            "last_evaluated_at": runtime.get("last_evaluated_at"),
            "last_error_type": runtime.get("last_error_type"),
            "cycles": int(runtime.get("cycles") or 0),
            "scan_completed_at": runtime.get("scan_completed_at"),
            "observations": deepcopy(runtime.get("observations") or []),
            "thread_alive": bool(thread is not None and thread.is_alive()),
            "poll_seconds": POLL_SECONDS,
            "network_requests": 0,
            "scan_authority_changed": False,
            "trading_authority_changed": False,
            "audio_authority_changed": False,
        }


def _metric(record: dict, *names: str) -> float | None:
    for name in names:
        value = _number(record.get(name))
        if value is not None:
            return value
    return None


def _canonical_label(record: dict) -> str:
    for key in (
        "candidate_status",
        "opportunity_state",
        "state",
        "status",
    ):
        value = record.get(key)
        if isinstance(value, dict):
            value = value.get("state")
        text = str(value or "").strip()
        if text:
            return text
    return "Current scan candidate"


def _live_regime(
    *,
    checked: int,
    above_vwap: bool,
    st_bullish: bool,
    fresh_flip: bool,
    participation_ok: bool,
    expansion_ok: bool,
    flow_accel: float | None,
    dollar_flow_accel: float | None,
    live_vwap_distance: float | None,
) -> str:
    """Describe live tape regime without changing Walter's canonical scan state."""
    flow = max(
        value
        for value in (
            flow_accel if flow_accel is not None else float("-inf"),
            dollar_flow_accel if dollar_flow_accel is not None else float("-inf"),
        )
    )
    breakout = bool(
        checked >= LIVE_BREAKOUT_MIN_BOXES
        and above_vwap
        and st_bullish
        and participation_ok
        and expansion_ok
        and flow >= LIVE_BREAKOUT_FLOW_MIN
    )
    if breakout:
        if (
            live_vwap_distance is not None
            and live_vwap_distance > LIVE_EXTENDED_VWAP_PCT
        ):
            return "ACTIVE RUNNER · EXTENDED"
        return "BREAKOUT ACTIVE"
    if fresh_flip:
        return "IGNITION"
    return "WATCHING"


def _evaluate_record(record: dict, provider, now: datetime) -> dict | None:
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    # initialize=False is critical: this may read the in-memory tick cache only.
    try:
        live_price = (provider.latest_trades([symbol], initialize=False) or {}).get(symbol)
    except Exception:
        live_price = None
    live_price = _number(live_price)
    if live_price is None:
        live_price = _number(record.get("price") or record.get("last_price"))

    try:
        from . import gs396_live_30s_tripwire as gs396

        enriched = gs396.enrich_record_with_live_30s(record, provider, now)
    except Exception:
        enriched = dict(record)

    tripwire = dict(enriched.get("thirty_second_tripwire") or {})
    vwap = _metric(record, "vwap_value", "current_vwap")
    participation = _metric(
        record,
        "participation_surge_score",
        "participation_score",
    )
    expansion = _metric(record, "expansion_quality", "expansion_score")
    flow_accel = _number(tripwire.get("volume_acceleration_30s"))
    dollar_flow_accel = _number(tripwire.get("dollar_flow_acceleration_30s"))

    from . import scanner_v2

    participation_floor = float(scanner_v2.TRIGGER_SURGE_MIN_SCORE)
    expansion_floor = float(scanner_v2.TRIGGER_EXPANSION_QUALITY_MIN)

    live_vwap_distance = None
    above_last_scan_vwap = False
    if live_price is not None and vwap not in (None, 0):
        live_vwap_distance = (live_price / float(vwap) - 1.0) * 100.0
        above_last_scan_vwap = live_price >= float(vwap)

    st_bullish = bool(tripwire.get("bullish"))
    fresh_flip = bool(tripwire.get("fresh_flip"))
    participation_ok = bool(
        participation is not None and participation >= participation_floor
    )
    expansion_ok = bool(expansion is not None and expansion >= expansion_floor)

    boxes = {
        "live_price_above_last_scan_vwap": above_last_scan_vwap,
        "genuine_30s_st_bullish": st_bullish,
        "fresh_genuine_30s_st_flip": fresh_flip,
        "last_scan_participation_at_trigger_floor": participation_ok,
        "last_scan_expansion_at_trigger_floor": expansion_ok,
    }
    checked = sum(bool(value) for value in boxes.values())

    # Keep the operator surface focused. A fresh flip is always noteworthy;
    # otherwise require at least three simultaneous boxes.
    if not fresh_flip and checked < MIN_BOXES_VISIBLE:
        return None

    scan_price = _metric(record, "price", "last_price")
    move_from_scan = None
    if live_price is not None and scan_price not in (None, 0):
        move_from_scan = (live_price / float(scan_price) - 1.0) * 100.0

    live_regime = _live_regime(
        checked=checked,
        above_vwap=above_last_scan_vwap,
        st_bullish=st_bullish,
        fresh_flip=fresh_flip,
        participation_ok=participation_ok,
        expansion_ok=expansion_ok,
        flow_accel=flow_accel,
        dollar_flow_accel=dollar_flow_accel,
        live_vwap_distance=live_vwap_distance,
    )

    return {
        "symbol": symbol,
        "canonical_state": _canonical_label(record),
        "live_regime": live_regime,
        "live_price": live_price,
        "last_scan_price": scan_price,
        "move_from_scan_pct": (
            round(move_from_scan, 3) if move_from_scan is not None else None
        ),
        "last_scan_vwap": vwap,
        "live_vs_last_scan_vwap_pct": (
            round(live_vwap_distance, 3)
            if live_vwap_distance is not None
            else None
        ),
        "participation_last_scan": participation,
        "participation_floor": participation_floor,
        "expansion_last_scan": expansion,
        "expansion_floor": expansion_floor,
        "thirty_second_st_bullish": st_bullish,
        "thirty_second_fresh_flip": fresh_flip,
        "thirty_second_flip_age_seconds": tripwire.get("last_flip_age_seconds"),
        "thirty_second_latest_closed": tripwire.get("latest_closed_timestamp"),
        "thirty_second_volume_acceleration": flow_accel,
        "thirty_second_dollar_flow_acceleration": dollar_flow_accel,
        "boxes": boxes,
        "boxes_checked": checked,
        "boxes_total": len(boxes),
        "awareness_only": True,
        "qualified_for_entry_changed": False,
        "candidate_state_changed": False,
    }


def evaluate_once(*, now: datetime | None = None) -> list[dict]:
    current = now or _utc_now()
    from .completed_scan import process_live_provider, process_live_scan_snapshot

    provider = process_live_provider()
    scan = process_live_scan_snapshot()
    if provider is None or scan is None:
        return []

    records = list(getattr(scan, "records", None) or [])[:MAX_RECORDS]
    observations = [
        observation
        for record in records
        if (observation := _evaluate_record(dict(record), provider, current))
        is not None
    ]
    observations.sort(
        key=lambda row: (
            not bool(row.get("thirty_second_fresh_flip")),
            -int(row.get("boxes_checked") or 0),
            -float(row.get("thirty_second_volume_acceleration") or 0.0),
            -float(row.get("participation_last_scan") or 0.0),
            str(row.get("symbol") or ""),
        )
    )
    return observations[:MAX_VISIBLE]


def _signature(row: dict) -> tuple:
    boxes = row.get("boxes") or {}
    return (
        bool(boxes.get("live_price_above_last_scan_vwap")),
        bool(boxes.get("genuine_30s_st_bullish")),
        bool(boxes.get("fresh_genuine_30s_st_flip")),
        bool(boxes.get("last_scan_participation_at_trigger_floor")),
        bool(boxes.get("last_scan_expansion_at_trigger_floor")),
    )


def _publish(observations: list[dict], now: datetime, scan_completed_at: Any) -> None:
    runtime = _runtime()
    current_iso = now.isoformat()
    with runtime["lock"]:
        signatures = runtime["signatures"]
        first_seen = runtime["first_seen"]
        changed_at = runtime["changed_at"]
        active_symbols = set()

        for row in observations:
            symbol = row["symbol"]
            active_symbols.add(symbol)
            sig = _signature(row)
            if symbol not in first_seen:
                first_seen[symbol] = current_iso
            if signatures.get(symbol) != sig:
                signatures[symbol] = sig
                changed_at[symbol] = current_iso
            row["first_seen_at"] = first_seen[symbol]
            row["last_box_change_at"] = changed_at.get(symbol) or current_iso
            row["evaluated_at"] = current_iso

        # A symbol can earn a fresh first-seen timestamp after it drops out and
        # later re-enters the live-watch condition.
        for symbol in list(first_seen):
            if symbol not in active_symbols:
                first_seen.pop(symbol, None)
                signatures.pop(symbol, None)
                changed_at.pop(symbol, None)

        runtime["observations"] = deepcopy(observations)
        runtime["last_evaluated_at"] = current_iso
        runtime["scan_completed_at"] = (
            scan_completed_at.isoformat()
            if hasattr(scan_completed_at, "isoformat")
            else str(scan_completed_at or "")
            or None
        )
        runtime["last_error_type"] = None
        runtime["status"] = "watching" if observations else "idle"
        runtime["cycles"] = int(runtime.get("cycles") or 0) + 1


def _loop(runtime: dict[str, Any]) -> None:
    while not runtime["stop"].is_set():
        now = _utc_now()
        try:
            from .completed_scan import process_live_scan_snapshot

            scan = process_live_scan_snapshot()
            observations = evaluate_once(now=now)
            _publish(
                observations,
                now,
                getattr(scan, "completed_at", None) if scan is not None else None,
            )
        except Exception as exc:
            with runtime["lock"]:
                runtime["status"] = "degraded"
                runtime["last_error_type"] = type(exc).__name__
                runtime["last_evaluated_at"] = now.isoformat()
        runtime["stop"].wait(POLL_SECONDS)


def ensure_running() -> dict:
    runtime = _runtime()
    with runtime["lock"]:
        thread = runtime.get("thread")
        if thread is not None and thread.is_alive():
            return snapshot()
        runtime["stop"].clear()
        runtime["status"] = "starting"
        thread = threading.Thread(
            target=_loop,
            args=(runtime,),
            name="walter-gs627-live-awareness",
            daemon=True,
        )
        runtime["thread"] = thread
        thread.start()
    return snapshot()


def _reset_for_tests() -> None:
    runtime = _runtime()
    with runtime["lock"]:
        runtime["stop"].set()
        thread = runtime.get("thread")
        builtins.__dict__[_RUNTIME_KEY] = _new_runtime()
    if isinstance(thread, threading.Thread) and thread.is_alive():
        thread.join(timeout=0.2)


__all__ = [
    "AUTHORITY",
    "POLL_SECONDS",
    "ensure_running",
    "evaluate_once",
    "snapshot",
]
