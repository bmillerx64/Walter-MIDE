"""GS344: scan-to-scan emergence/convergence guidance for Walter.

Walter's live discovery feeds can be frenetic around the open. A single snapshot
can say little about which name is becoming the durable play. GS344 therefore
adds presentation-only memory across recent scans and surfaces a non-entry
"EMERGING · WATCH FIRST" cue when price/trend structure remains constructive
while participation and expansion are materially improving.

This module does not change discovery, candidate membership, qualification,
scoring, thresholds, readiness, alerts, execution, orders, or trading logic.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic

MAX_HISTORY = 6
HISTORY_TTL_SECONDS = 12 * 60
MAX_VWAP_DISTANCE_PCT = 2.5
MIN_PARTICIPATION = 24.0
MIN_EXPANSION = 42.0
MIN_COMBINED_IMPROVEMENT = 12.0
MIN_SINGLE_METRIC_IMPROVEMENT = 8.0


@dataclass(frozen=True)
class EmergenceSnapshot:
    participation: float
    expansion: float
    volume: float
    vwap_distance_pct: float | None
    above_vwap: bool
    supertrend_bullish: bool
    fast_mover: bool
    seen_at: float


_history: dict[str, deque[EmergenceSnapshot]] = {}


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        try:
            value = record.get(key)
            if value is None or value == "":
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _above_vwap(record: dict) -> tuple[bool, float | None]:
    distance = _number(record, "vwap_distance_pct", "vwap_distance")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    above = (distance is not None and distance >= 0.0) or relation in {
        "above", "above_vwap", "reclaimed", "pass",
    }
    return above, distance


def _supertrend(record: dict) -> bool:
    return bool(
        record.get("supertrend_bullish")
        or record.get("supertrend_flip")
        or str(record.get("supertrend") or "").strip().lower() in {"bullish", "green", "up"}
    )


def _fast_mover(record: dict) -> bool:
    sources = {str(value or "").strip().lower() for value in record.get("sources") or []}
    ranks = record.get("ranks") or {}
    return "five_minute_movers" in sources or "five_minute_movers" in ranks


def snapshot(record: dict, *, seen_at: float | None = None) -> EmergenceSnapshot:
    above, distance = _above_vwap(record)
    return EmergenceSnapshot(
        participation=_number(record, "participation_score", "participation_surge_score", default=0.0) or 0.0,
        expansion=_number(record, "expansion_score", "expansion_quality", default=0.0) or 0.0,
        volume=_number(record, "volume", default=0.0) or 0.0,
        vwap_distance_pct=distance,
        above_vwap=above,
        supertrend_bullish=_supertrend(record),
        fast_mover=_fast_mover(record),
        seen_at=monotonic() if seen_at is None else seen_at,
    )


def emergence_signal(record: dict, history: list[EmergenceSnapshot] | tuple[EmergenceSnapshot, ...]) -> tuple[bool, str]:
    """Return a non-entry emergence signal when several scans are converging."""
    if len(history) < 2:
        return False, "insufficient scan history"

    current = snapshot(record)
    if not current.above_vwap:
        return False, "below VWAP"
    if current.vwap_distance_pct is not None and current.vwap_distance_pct > MAX_VWAP_DISTANCE_PCT:
        return False, "too extended"
    if not current.supertrend_bullish:
        return False, "SuperTrend not bullish"
    if current.participation < MIN_PARTICIPATION:
        return False, "participation too weak"
    if current.expansion < MIN_EXPANSION:
        return False, "expansion too weak"

    recent = list(history)[-3:]
    constructive = sum(1 for snap in recent if snap.above_vwap and snap.supertrend_bullish)
    if constructive < 2:
        return False, "structure not persistent"

    baseline = list(history)[0]
    p_delta = current.participation - baseline.participation
    e_delta = current.expansion - baseline.expansion
    combined = p_delta + e_delta
    improving = (
        combined >= MIN_COMBINED_IMPROVEMENT
        and (p_delta >= MIN_SINGLE_METRIC_IMPROVEMENT or e_delta >= MIN_SINGLE_METRIC_IMPROVEMENT)
    )

    newly_fast = current.fast_mover and not any(snap.fast_mover for snap in history)
    volume_advancing = not baseline.volume or current.volume > baseline.volume
    if not improving:
        return False, "scores not converging"
    if not (volume_advancing or newly_fast):
        return False, "attention not advancing"

    reason = f"participation/expansion improving +{combined:.0f}"
    if newly_fast:
        reason += "; newly active in 5-minute movers"
    return True, reason


def emergence_recommendation(record: dict, history) -> dict | None:
    ok, reason = emergence_signal(record, history)
    if not ok:
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "label": "EMERGING · WATCH FIRST",
        "message": f"Multi-scan evidence is converging: {reason}.",
        "guidance": (
            "Keep this chart near the front. This is not an entry call; require VWAP to hold, "
            "SuperTrend to stay bullish, and participation/expansion to continue improving."
        ),
    }


def apply_emergence_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
    now = monotonic() if now is None else now
    marked: list[dict] = []
    active: set[str] = set()

    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            marked.append(record)
            continue
        active.add(symbol)
        history = _history.setdefault(symbol, deque(maxlen=MAX_HISTORY))
        cue = emergence_recommendation(record, tuple(history))
        if cue is not None:
            copy = dict(record)
            copy["_gs344_emergence"] = cue
            marked.append(copy)
        else:
            marked.append(record)
        history.append(snapshot(record, seen_at=now))

    stale = [
        symbol
        for symbol, history in _history.items()
        if symbol not in active and history and now - history[-1].seen_at > HISTORY_TTL_SECONDS
    ]
    for symbol in stale:
        _history.pop(symbol, None)
    return marked


def reset_emergence_memory() -> None:
    _history.clear()


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install presentation-only emergence memory after existing GS cues."""
    from . import ui

    current_render = ui.render_walter_mission_control
    if getattr(current_render, "_gs344_emergence_convergence_engine", False):
        return

    def render_with_emergence(records: list[dict]) -> None:
        return current_render(apply_emergence_marks(records))

    _inherit_wrapper_contract(render_with_emergence, current_render)
    render_with_emergence._gs344_emergence_convergence_engine = True
    render_with_emergence._gs344_original = current_render
    ui.render_walter_mission_control = render_with_emergence

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation) and not getattr(current_recommendation, "_gs344_emergence_convergence_engine", False):
        def recommendation_with_emergence(record: dict):
            base = current_recommendation(record)
            cue = record.get("_gs344_emergence") if isinstance(record, dict) else None
            if not isinstance(cue, dict):
                return base

            base_label = str(base.get("label") or "").upper() if isinstance(base, dict) else ""
            stronger = ("MOMENTUM IGNITING", "LOOK NOW", "WATCH FOR ENTRY", "ENTRY", "CHASE", "RESET REQUIRED")
            if any(token in base_label for token in stronger):
                return base
            return cue

        _inherit_wrapper_contract(recommendation_with_emergence, current_recommendation)
        recommendation_with_emergence._gs344_emergence_convergence_engine = True
        recommendation_with_emergence._gs344_original = current_recommendation
        ui.mission_control_recommendation = recommendation_with_emergence
