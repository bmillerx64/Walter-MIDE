"""GS345: persistent-leader escalation for durable intraday runners.

GS343 widened discovery to all four native Webull attention feeds and GS344 added
scan-to-scan convergence memory. GS345 uses that same presentation-layer idea to
recognize a different regime: a symbol that keeps strengthening across several
scans and is becoming a durable market leader rather than a one-print mover.

The cue is intentionally non-entry guidance. It does not change discovery,
candidate membership, qualification, scoring, thresholds, readiness, alerts,
execution, orders, or trading logic.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import monotonic

MAX_HISTORY = 8
HISTORY_TTL_SECONDS = 15 * 60
MAX_VWAP_DISTANCE_PCT = 3.0
MIN_GAIN_PCT = 20.0
MIN_PARTICIPATION = 40.0
MIN_EXPANSION = 48.0
MAX_NATIVE_RANK = 10
MIN_PERSISTENT_SCANS = 3


@dataclass(frozen=True)
class LeaderSnapshot:
    gain_pct: float
    participation: float
    expansion: float
    volume: float
    vwap_distance_pct: float | None
    above_vwap: bool
    supertrend_bullish: bool
    native_rank: int | None
    halted: bool
    seen_at: float


_history: dict[str, deque[LeaderSnapshot]] = {}


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


def _native_rank(record: dict) -> int | None:
    ranks = record.get("ranks") or {}
    candidates = []
    for key in ("five_minute_movers", "day_gainers", "relative_volume", "absolute_volume"):
        try:
            rank = int(float(ranks.get(key)))
            if rank > 0:
                candidates.append(rank)
        except (TypeError, ValueError):
            pass
    return min(candidates) if candidates else None


def snapshot(record: dict, *, seen_at: float | None = None) -> LeaderSnapshot:
    above, distance = _above_vwap(record)
    return LeaderSnapshot(
        gain_pct=_number(record, "change_ratio", "pct_change", "change_pct", default=0.0) or 0.0,
        participation=_number(record, "participation_score", "participation_surge_score", default=0.0) or 0.0,
        expansion=_number(record, "expansion_score", "expansion_quality", default=0.0) or 0.0,
        volume=_number(record, "volume", default=0.0) or 0.0,
        vwap_distance_pct=distance,
        above_vwap=above,
        supertrend_bullish=_supertrend(record),
        native_rank=_native_rank(record),
        halted=bool(record.get("halted") or record.get("is_halted") or record.get("suspended")),
        seen_at=monotonic() if seen_at is None else seen_at,
    )


def persistent_leader_signal(record: dict, history) -> tuple[bool, str]:
    """Return True when a symbol is proving durable leadership across scans."""
    if len(history) < MIN_PERSISTENT_SCANS - 1:
        return False, "insufficient scan history"

    current = snapshot(record)
    if current.halted:
        return False, "currently halted"
    if not current.above_vwap:
        return False, "below VWAP"
    if current.vwap_distance_pct is not None and current.vwap_distance_pct > MAX_VWAP_DISTANCE_PCT:
        return False, "too extended"
    if not current.supertrend_bullish:
        return False, "SuperTrend not bullish"
    if current.gain_pct < MIN_GAIN_PCT:
        return False, "gain not leader-class"
    if current.participation < MIN_PARTICIPATION:
        return False, "participation too weak"
    if current.expansion < MIN_EXPANSION:
        return False, "expansion too weak"
    if current.native_rank is None or current.native_rank > MAX_NATIVE_RANK:
        return False, "not persistent in native leader feeds"

    recent = list(history)[-(MIN_PERSISTENT_SCANS - 1):] + [current]
    constructive = sum(1 for snap in recent if snap.above_vwap and snap.supertrend_bullish)
    ranked = sum(1 for snap in recent if snap.native_rank is not None and snap.native_rank <= MAX_NATIVE_RANK)
    if constructive < MIN_PERSISTENT_SCANS:
        return False, "structure not persistent"
    if ranked < MIN_PERSISTENT_SCANS:
        return False, "native leadership not persistent"

    first = recent[0]
    gain_advancing = current.gain_pct >= first.gain_pct + 8.0
    volume_advancing = not first.volume or current.volume >= first.volume * 1.35
    evidence_advancing = (
        current.participation + current.expansion
        >= first.participation + first.expansion + 10.0
    )
    rank_improving = (
        first.native_rank is not None
        and current.native_rank is not None
        and current.native_rank <= first.native_rank
    )
    if sum((gain_advancing, volume_advancing, evidence_advancing, rank_improving)) < 3:
        return False, "leadership not strengthening"

    prior_halt = any(snap.halted for snap in history)
    reason = "persistent top-10 leadership with strengthening price/volume evidence"
    if prior_halt:
        reason += "; resumed constructively after a halt"
    return True, reason


def leader_recommendation(record: dict, history) -> dict | None:
    ok, reason = persistent_leader_signal(record, history)
    if not ok:
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "label": "LEADER · STAY ON IT",
        "message": f"This name is proving durable: {reason}.",
        "guidance": (
            "Keep this chart at the front. This is not an entry call; require VWAP and SuperTrend "
            "to hold and wait for a disciplined continuation or reset rather than chasing."
        ),
    }


def apply_leader_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
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
        cue = leader_recommendation(record, tuple(history))
        if cue is not None:
            copy = dict(record)
            copy["_gs345_leader"] = cue
            marked.append(copy)
        else:
            marked.append(record)
        history.append(snapshot(record, seen_at=now))

    stale = [
        symbol for symbol, history in _history.items()
        if symbol not in active and history and now - history[-1].seen_at > HISTORY_TTL_SECONDS
    ]
    for symbol in stale:
        _history.pop(symbol, None)
    return marked


def reset_leader_memory() -> None:
    _history.clear()


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install persistent-leader guidance after GS344 convergence memory."""
    from . import ui

    current_render = ui.render_walter_mission_control
    if getattr(current_render, "_gs345_persistent_leader_escalation", False):
        return

    def render_with_leaders(records: list[dict]) -> None:
        return current_render(apply_leader_marks(records))

    _inherit_wrapper_contract(render_with_leaders, current_render)
    render_with_leaders._gs345_persistent_leader_escalation = True
    render_with_leaders._gs345_original = current_render
    ui.render_walter_mission_control = render_with_leaders

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation) and not getattr(current_recommendation, "_gs345_persistent_leader_escalation", False):
        def recommendation_with_leader(record: dict):
            base = current_recommendation(record)
            cue = record.get("_gs345_leader") if isinstance(record, dict) else None
            if not isinstance(cue, dict):
                return base

            base_label = str(base.get("label") or "").upper() if isinstance(base, dict) else ""
            stronger = ("MOMENTUM IGNITING", "WATCH FOR ENTRY", "ENTRY", "CHASE", "RESET REQUIRED")
            if any(token in base_label for token in stronger):
                return base
            return cue

        _inherit_wrapper_contract(recommendation_with_leader, current_recommendation)
        recommendation_with_leader._gs345_persistent_leader_escalation = True
        recommendation_with_leader._gs345_original = current_recommendation
        ui.mission_control_recommendation = recommendation_with_leader
