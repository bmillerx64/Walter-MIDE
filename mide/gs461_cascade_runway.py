"""GS461: expose the next slower SuperTrend domino behind GS460 ignition compression.

RETO live training on 2026-09-15 clarified a second operator insight after GS460's
bottom-up 30s -> 1m -> 3m -> 5m flip-price compression.  Once the fast ladder is
compressed and supported by real buy-in, the operator watches whether the next slower
SuperTrend barriers are already bullish or close enough to plausibly join the move.
A non-contiguous slower frame can also matter as background support (for example 10m
bullish, 15m/30m not yet flipped, while 1h is already bullish).

GS461 makes that context explicit without predicting a future flip.  It reports the
*current* SuperTrend line/barrier on 10m/15m/30m/1h and the percentage gap from the
current chart close when that frame remains bearish.  The line can move as a bar
develops, so the gap is deliberately described as runway/proximity, not a guaranteed
future flip price.

Performance/safety contract:
- GS461 runs only for records with an active GS460 compression signal;
- 10m/15m line truth is reused when already present; otherwise it is reconstructed
  locally from Walter's already-owned 1-minute history;
- 30m/1h are local resamples of that same history; no provider request is added;
- opportunity state is never changed by GS461 -- it only enriches a GS460 LOOK NOW or
  CHASE / WAIT explanation and its existing tier-2 spoken alert;
- qualification, readiness, VWAP anti-chase, session authority, execution and orders
  are untouched.  Premarket/after-hours runway evidence remains attention only.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

import pandas as pd

from .indicators import resample_ohlcv, supertrend

RUNWAY_ORDER = ("10m", "15m", "30m", "1h")
_RULES = {"10m": "10min", "15m": "15min", "30m": "30min", "1h": "60min"}
AUTHORITY = "OPERATOR_ATTENTION_ONLY"
SOURCE = "existing GS460/GS423 evidence + local resample of already-fetched current-session 1m bars"
_PROVENANCE = "ST_CASCADE_RUNWAY"
_INSTALL_GENERATION = object()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _status_payload(
    label: str,
    *,
    available: bool,
    bullish: bool = False,
    close: float | None = None,
    supertrend_value: float | None = None,
    source: str,
) -> dict:
    close = _number(close)
    st_value = _number(supertrend_value)
    gap = None
    if available and close not in (None, 0) and st_value is not None:
        gap = abs(st_value - close) / close * 100.0
    return {
        "timeframe": label,
        "available": bool(available),
        "bullish": bool(bullish) if available else False,
        "current_close": close,
        "current_supertrend": st_value,
        "line_gap_pct": round(gap, 3) if gap is not None else None,
        "barrier_gap_pct": (
            0.0 if available and bullish else round(gap, 3) if gap is not None else None
        ),
        "relation": (
            "support" if available and bullish else "overhead_barrier" if available else "unavailable"
        ),
        "source": source,
    }


def _existing_status(record: dict, label: str) -> dict | None:
    """Reuse current 10m/15m line truth when GS455/423 already retained it."""
    from . import gs460_st_flip_compression_ignition as gs460

    if label not in {"10m", "15m"}:
        return None
    detail = gs460._tf_detail(record, label)
    if not detail:
        return None
    line_cross = dict(detail.get("line_cross") or {})
    close = _number(detail.get("current_close"))
    st_value = _number(line_cross.get("latest_supertrend_value"))
    bullish = bool(detail.get("current_bullish"))
    # A retained bullish state is still useful even if the exact latest line value
    # was not preserved.  A bearish frame needs the line value before we describe a
    # distance/barrier, otherwise fall back to local reconstruction.
    if bullish and close is not None:
        return _status_payload(
            label,
            available=True,
            bullish=True,
            close=close,
            supertrend_value=st_value,
            source="retained GS455/423 timeframe evidence",
        )
    if close is not None and st_value is not None:
        return _status_payload(
            label,
            available=True,
            bullish=False,
            close=close,
            supertrend_value=st_value,
            source="retained GS455/423 timeframe evidence",
        )
    return None


def _local_status(day: pd.DataFrame, label: str) -> dict:
    """Build one slower-frame status locally from already-owned 1m history."""
    if day is None or day.empty:
        return _status_payload(label, available=False, source="no current-session history")
    rule = _RULES[label]
    try:
        frame = resample_ohlcv(day, rule)
    except Exception:
        return _status_payload(label, available=False, source=f"local {rule} resample failed")
    if frame is None or frame.empty or len(frame) < 2:
        return _status_payload(label, available=False, source=f"local {rule} resample not ready")

    try:
        st_line, trend = supertrend(frame, 10, 3)
    except Exception:
        return _status_payload(label, available=False, source=f"local {rule} SuperTrend not ready")

    close = _number(frame["close"].astype(float).iloc[-1])
    st_value = _number(st_line.iloc[-1]) if len(st_line) else None
    if close is None or st_value is None or not len(trend):
        return _status_payload(label, available=False, source=f"local {rule} SuperTrend not ready")
    return _status_payload(
        label,
        available=True,
        bullish=bool(trend.fillna(False).astype(bool).iloc[-1]),
        close=close,
        supertrend_value=st_value,
        source=f"local {rule} resample from Stage-6 current-session 1m history",
    )


def summarize_runway(compression: dict, statuses: dict[str, dict]) -> dict:
    """Summarize the factual slower-frame path without inventing a probability model."""
    ordered = [dict(statuses.get(label) or {}) for label in RUNWAY_ORDER]
    available = [item["timeframe"] for item in ordered if item.get("available")]
    bullish = [item["timeframe"] for item in ordered if item.get("available") and item.get("bullish")]

    contiguous: list[str] = []
    first_unresolved: dict | None = None
    first_index: int | None = None
    for index, item in enumerate(ordered):
        if item.get("available") and item.get("bullish"):
            if first_unresolved is None:
                contiguous.append(item["timeframe"])
            continue
        first_unresolved = item
        first_index = index
        break

    future_support: list[str] = []
    if first_index is not None:
        future_support = [
            item["timeframe"]
            for item in ordered[first_index + 1 :]
            if item.get("available") and item.get("bullish")
        ]

    next_barrier = None
    blocked_by_unavailable = None
    if first_unresolved:
        if first_unresolved.get("available") and not first_unresolved.get("bullish"):
            next_barrier = {
                "timeframe": first_unresolved.get("timeframe"),
                "barrier_gap_pct": first_unresolved.get("barrier_gap_pct"),
                "current_close": first_unresolved.get("current_close"),
                "current_supertrend": first_unresolved.get("current_supertrend"),
            }
        elif not first_unresolved.get("available"):
            blocked_by_unavailable = first_unresolved.get("timeframe")

    active = bool(compression.get("active") and available)
    return {
        "active": active,
        "lower_stage": compression.get("stage"),
        "lower_depth": int(compression.get("depth") or 0),
        "lower_sequence": compression.get("sequence") or "",
        "frames": {item.get("timeframe"): item for item in ordered if item.get("timeframe")},
        "available_frames": available,
        "bullish_frames": bullish,
        "contiguous_slower_bullish": contiguous,
        "next_barrier": next_barrier,
        "blocked_by_unavailable": blocked_by_unavailable,
        "future_bullish_support": future_support,
        "authority": AUTHORITY,
        "source": SOURCE,
        "additional_history_requests": 0,
        "entry_authority_changed": False,
    }


def build_cascade_runway(record: dict, raw_rows, client) -> dict:
    """Build slower-frame runway only after GS460 bottom-up compression is active."""
    from . import gs378_live_vwap_st_crossover as gs378
    from . import gs460_st_flip_compression_ignition as gs460

    compression = gs460.st_flip_compression(record)
    if not compression.get("active"):
        return {
            "active": False,
            "reason": "no_active_gs460_compression",
            "authority": AUTHORITY,
            "source": SOURCE,
            "additional_history_requests": 0,
            "entry_authority_changed": False,
        }

    try:
        frame = client.bars_frame(raw_rows or [])
        day = gs378._eastern_day(frame)
    except Exception:
        day = pd.DataFrame()

    statuses: dict[str, dict] = {}
    for label in RUNWAY_ORDER:
        existing = _existing_status(record, label)
        statuses[label] = existing if existing is not None else _local_status(day, label)
    return summarize_runway(compression, statuses)


def _runway_text(runway: dict) -> str:
    if not runway.get("active"):
        return ""
    parts: list[str] = []
    contiguous = list(runway.get("contiguous_slower_bullish") or [])
    if contiguous:
        parts.append(" / ".join(contiguous) + " already bullish")
    barrier = dict(runway.get("next_barrier") or {})
    if barrier:
        label = barrier.get("timeframe")
        gap = _number(barrier.get("barrier_gap_pct"))
        if gap is not None:
            parts.append(f"next {label} SuperTrend line {gap:.1f}% away")
        else:
            parts.append(f"next {label} SuperTrend barrier present")
    unavailable = runway.get("blocked_by_unavailable")
    if unavailable:
        parts.append(f"{unavailable} runway not yet measurable")
    future = list(runway.get("future_bullish_support") or [])
    if future:
        parts.append("later " + " / ".join(future) + " already bullish")
    return "; ".join(parts)


def _state_with_runway(original, record: dict) -> dict:
    base = original(record)
    runway = dict(record.get("st_cascade_runway") or {})
    if not runway.get("active"):
        return base
    provenance = list(base.get("attention_provenance") or [])
    # GS461 describes only the GS460 thesis; never enrich an unrelated state merely
    # because the record happens to carry slower-frame data.
    if "ST_FLIP_PRICE_COMPRESSION" not in provenance:
        return base

    text = _runway_text(runway)
    if not text:
        return base
    view = deepcopy(base)
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_cascade_runway"] = runway
    reason = str(view.get("reason") or "").rstrip()
    if "Cascade runway:" not in reason:
        view["reason"] = f"{reason} Cascade runway: {text}.".strip()
    next_step = str(view.get("next_step") or "").rstrip()
    if "current SuperTrend line" not in next_step:
        view["next_step"] = (
            f"{next_step} Treat the slower-frame gap as proximity to the current SuperTrend line, "
            "not a guaranteed future flip price."
        ).strip()
    return view


def _install_evidence() -> None:
    """Wrap GS423's final live convergence handoff; do not add provider work."""
    from . import gs378_live_vwap_st_crossover as gs378

    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs461_install_generation", None) is _INSTALL_GENERATION:
        return

    @wraps(current)
    def apply_with_runway(records, current_session_raw, current_session_30s_raw, client):
        updated = current(records, current_session_raw, current_session_30s_raw, client)
        measured = 0
        for record in updated or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            evidence = build_cascade_runway(
                record,
                (current_session_raw or {}).get(symbol) or [],
                client,
            )
            if evidence.get("active"):
                record["st_cascade_runway"] = evidence
                measured += 1

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs461_cascade_runway"] = {
                "authority": AUTHORITY,
                "records_measured": measured,
                "timeframes": list(RUNWAY_ORDER),
                "additional_history_requests": 0,
                "entry_authority_changed": False,
                "qualification_changed": False,
                "readiness_changed": False,
                "execution_changed": False,
            }
        return updated

    apply_with_runway._gs461_cascade_runway = True
    apply_with_runway._gs461_original = current
    apply_with_runway._gs461_install_generation = _INSTALL_GENERATION
    gs378.apply_live_vwap_truth = apply_with_runway


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
    if getattr(current, "_gs461_cascade_runway", False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return _state_with_runway(current, record)

        _inherit(calibrated, current)
        calibrated._gs461_cascade_runway = True
        calibrated._gs461_original = current
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _alert_runway(records: list[dict]) -> str:
    from . import gs460_st_flip_compression_ignition as gs460

    choices = []
    for record in records or []:
        compression = gs460.st_flip_compression(record)
        runway = dict(record.get("st_cascade_runway") or {})
        if not compression.get("fresh_join") or not runway.get("active"):
            continue
        barrier = dict(runway.get("next_barrier") or {})
        gap = _number(barrier.get("barrier_gap_pct"))
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
    _depth, _gap_rank, _record, runway = max(choices, key=lambda item: (item[0], item[1]))
    text = _runway_text(runway)
    return f" Cascade runway. {text}." if text else ""


def _install_alerts() -> None:
    from . import escalation

    current = escalation.escalation_alert_phrase
    if getattr(current, "_gs461_cascade_runway", False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        phrase = str(current(rows) or "")
        # Only annotate GS460's existing LOOK NOW delivery. GS461 never manufactures
        # a new audible transition or changes semantic tier/chime count.
        if "IGNITION COMPRESSION" not in phrase.upper():
            return phrase
        runway = _alert_runway(rows)
        if runway and "CASCADE RUNWAY" not in phrase.upper():
            return phrase.rstrip() + runway
        return phrase

    _inherit(alert_phrase, current)
    alert_phrase._gs461_cascade_runway = True
    alert_phrase._gs461_original = current
    escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install after GS423 and GS460 so runway sees the final retained timeframe truth."""
    _install_evidence()
    _install_state()
    _install_alerts()
