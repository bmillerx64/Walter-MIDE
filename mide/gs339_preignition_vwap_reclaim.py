"""GS339: surface early VWAP-reclaim alignment before the move becomes chase-only.

Presentation-only operator guidance. This module does not change discovery,
qualification, scoring, thresholds, readiness, ranking, alerts, execution, or
candidate membership. It adds a lower-intensity watch cue for a narrow class of
constructive transitions that live review showed can precede fast continuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

MAX_VWAP_DISTANCE_PCT = 2.5
MIN_PARTICIPATION = 28.0
MIN_EXPANSION = 45.0
MIN_COMBINED_DELTA = 8.0
SNAPSHOT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class Snapshot:
    participation: float
    expansion: float
    volume: float
    above_vwap: bool
    seen_at: float


_previous: dict[str, Snapshot] = {}


def _number(record: dict, key: str, default: float | None = None) -> float | None:
    try:
        value = record.get(key)
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _above_vwap(record: dict) -> bool:
    distance = _number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    return (distance is not None and distance >= 0.0) or relation in {
        "above",
        "above_vwap",
        "reclaimed",
    }


def snapshot(record: dict, *, seen_at: float | None = None) -> Snapshot:
    return Snapshot(
        participation=_number(record, "participation_score", 0.0) or 0.0,
        expansion=_number(record, "expansion_score", 0.0) or 0.0,
        volume=_number(record, "volume", 0.0) or 0.0,
        above_vwap=_above_vwap(record),
        seen_at=monotonic() if seen_at is None else seen_at,
    )


def preignition_watch(record: dict, prior: Snapshot | None) -> tuple[bool, str]:
    """Detect a constructive reclaim/strengthening state without calling entry."""
    if prior is None:
        return False, "no prior scan"
    if not _above_vwap(record):
        return False, "below VWAP"

    distance = _number(record, "vwap_distance_pct")
    if distance is not None and distance > MAX_VWAP_DISTANCE_PCT:
        return False, "too extended"

    supertrend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    if not supertrend:
        return False, "SuperTrend not bullish"

    participation = _number(record, "participation_score", 0.0) or 0.0
    expansion = _number(record, "expansion_score", 0.0) or 0.0
    if participation < MIN_PARTICIPATION:
        return False, "participation too weak"
    if expansion < MIN_EXPANSION:
        return False, "expansion too weak"

    p_delta = participation - prior.participation
    e_delta = expansion - prior.expansion
    reclaimed = not prior.above_vwap
    strengthening = (p_delta + e_delta) >= MIN_COMBINED_DELTA and (p_delta > 0 or e_delta > 0)
    if not (reclaimed or strengthening):
        return False, "no fresh reclaim or strengthening"

    volume = _number(record, "volume", 0.0) or 0.0
    fresh_catalyst = bool(
        str(record.get("headline") or "").strip()
        or record.get("fresh_news")
        or record.get("news_catalyst")
        or record.get("has_catalyst")
        or record.get("catalyst_confirmed")
    )
    if not fresh_catalyst:
        if volume < 250_000:
            return False, "volume too light without catalyst"
        if prior.volume and volume <= prior.volume:
            return False, "volume not advancing"

    reason = "VWAP reclaimed" if reclaimed else f"scores improving +{p_delta + e_delta:.0f}"
    return True, reason


def watch_recommendation(record: dict, prior: Snapshot | None):
    watching, reason = preignition_watch(record, prior)
    if not watching:
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "label": "SETUP BUILDING · WATCH CLOSELY",
        "message": f"Price/trend alignment is constructive and {reason}; the setup is not entry-ready yet.",
        "guidance": "Keep the chart open. Require price to hold above VWAP, SuperTrend to remain bullish, and participation/expansion to keep strengthening before acting.",
    }


def apply_preignition_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
    now = monotonic() if now is None else now
    marked: list[dict] = []
    current_symbols: set[str] = set()

    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            marked.append(record)
            continue
        current_symbols.add(symbol)
        prior = _previous.get(symbol)
        recommendation = watch_recommendation(record, prior)
        if recommendation is not None:
            copy = dict(record)
            copy["_gs339_preignition_watch"] = recommendation
            marked.append(copy)
        else:
            marked.append(record)
        _previous[symbol] = snapshot(record, seen_at=now)

    stale = [
        symbol
        for symbol, prior in _previous.items()
        if symbol not in current_symbols and now - prior.seen_at > SNAPSHOT_TTL_SECONDS
    ]
    for symbol in stale:
        _previous.pop(symbol, None)
    return marked


def reset_preignition_memory() -> None:
    _previous.clear()


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    current_render = ui.render_walter_mission_control
    if getattr(current_render, "_gs339_preignition_vwap_reclaim", False):
        return

    def render_with_preignition_watch(records: list[dict]) -> None:
        return current_render(apply_preignition_marks(records))

    _inherit_wrapper_contract(render_with_preignition_watch, current_render)
    render_with_preignition_watch._gs339_preignition_vwap_reclaim = True
    render_with_preignition_watch._gs339_original = current_render
    ui.render_walter_mission_control = render_with_preignition_watch

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation) and not getattr(current_recommendation, "_gs339_preignition_vwap_reclaim", False):
        def recommendation_with_preignition_watch(record: dict):
            base = current_recommendation(record)
            cue = record.get("_gs339_preignition_watch") if isinstance(record, dict) else None
            if not isinstance(cue, dict):
                return base

            base_label = str(base.get("label") or "").upper() if isinstance(base, dict) else ""
            # Never dilute stronger existing operator language.
            if any(token in base_label for token in ("MOMENTUM IGNITING", "LOOK NOW", "ENTRY", "CHASE", "RESET REQUIRED")):
                return base
            return cue

        _inherit_wrapper_contract(recommendation_with_preignition_watch, current_recommendation)
        recommendation_with_preignition_watch._gs339_preignition_vwap_reclaim = True
        recommendation_with_preignition_watch._gs339_original = current_recommendation
        ui.mission_control_recommendation = recommendation_with_preignition_watch
