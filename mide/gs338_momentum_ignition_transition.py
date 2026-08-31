"""GS338: detect momentum transitions before they become chase-only moves.

Presentation-only. This module watches consecutive Radar snapshots and upgrades
operator language when a symbol is strengthening while still reasonably close
to VWAP. It does not change discovery, qualification, scoring, thresholds,
readiness, ranking, alerts, execution, or candidate membership.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

MAX_VWAP_DISTANCE_PCT = 5.0
MIN_PARTICIPATION = 40.0
MIN_EXPANSION = 55.0
MIN_SCORE_DELTA = 8.0
MIN_COMBINED_DELTA = 14.0
SNAPSHOT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class Snapshot:
    participation: float
    expansion: float
    volume: float
    vwap_distance_pct: float | None
    supertrend_bullish: bool
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
        vwap_distance_pct=_number(record, "vwap_distance_pct"),
        supertrend_bullish=bool(record.get("supertrend_bullish") or record.get("supertrend_flip")),
        seen_at=monotonic() if seen_at is None else seen_at,
    )


def momentum_ignition(record: dict, prior: Snapshot | None) -> tuple[bool, str]:
    """Return whether the current record is materially accelerating.

    The cue is intentionally strict: Walter must already have constructive
    structure, remain within 5% of VWAP, and show a meaningful score transition
    from the prior scan. A single strong static reading is not enough.
    """
    if prior is None:
        return False, "no prior scan"
    if not _above_vwap(record):
        return False, "not above VWAP"

    current = snapshot(record, seen_at=prior.seen_at)
    if current.vwap_distance_pct is not None and current.vwap_distance_pct > MAX_VWAP_DISTANCE_PCT:
        return False, "already extended"
    if not current.supertrend_bullish:
        return False, "SuperTrend not bullish"
    if current.participation < MIN_PARTICIPATION:
        return False, "participation still weak"
    if current.expansion < MIN_EXPANSION:
        return False, "expansion still weak"

    p_delta = current.participation - prior.participation
    e_delta = current.expansion - prior.expansion
    score_transition = (
        p_delta >= MIN_SCORE_DELTA
        or e_delta >= MIN_SCORE_DELTA
    ) and (p_delta + e_delta >= MIN_COMBINED_DELTA)
    if not score_transition:
        return False, "no meaningful score acceleration"

    # Cumulative day volume should not decline. A positive increase is useful
    # corroboration, but score acceleration remains authoritative because some
    # providers round or lag the volume field between scans.
    if current.volume and prior.volume and current.volume < prior.volume:
        return False, "volume evidence regressed"

    return True, f"participation +{p_delta:.0f}, expansion +{e_delta:.0f}"


def ignition_recommendation(record: dict, prior: Snapshot | None):
    igniting, reason = momentum_ignition(record, prior)
    if not igniting:
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "label": "MOMENTUM IGNITING · LOOK NOW",
        "message": f"Evidence strengthened sharply since the prior scan ({reason}) while price is still near VWAP.",
        "guidance": "Open the chart now. Confirm VWAP hold/reclaim, SuperTrend, real volume, and normal Walter entry evidence. If price extends beyond the acceptable VWAP zone, do not chase.",
    }


def apply_transition_marks(records: list[dict], *, now: float | None = None) -> list[dict]:
    """Attach presentation-only transition metadata and advance the cache."""
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
        recommendation = ignition_recommendation(record, prior)
        if recommendation is not None:
            copy = dict(record)
            copy["_gs338_momentum_ignition"] = recommendation
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


def reset_transition_memory() -> None:
    _previous.clear()


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    current_render = ui.render_walter_mission_control
    if getattr(current_render, "_gs338_momentum_ignition_transition", False):
        return

    def render_with_momentum_transition(records: list[dict]) -> None:
        return current_render(apply_transition_marks(records))

    _inherit_wrapper_contract(render_with_momentum_transition, current_render)
    render_with_momentum_transition._gs338_momentum_ignition_transition = True
    render_with_momentum_transition._gs338_original = current_render
    ui.render_walter_mission_control = render_with_momentum_transition

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation) and not getattr(current_recommendation, "_gs338_momentum_ignition_transition", False):
        def recommendation_with_momentum_transition(record: dict):
            ignition = record.get("_gs338_momentum_ignition") if isinstance(record, dict) else None
            base = current_recommendation(record)
            if not isinstance(ignition, dict):
                return base

            # Never use the transition cue to overrule an explicit chase/extended
            # warning from the existing recommendation stack.
            if isinstance(base, dict) and "CHASE" in str(base.get("label") or "").upper():
                return base
            return ignition

        _inherit_wrapper_contract(recommendation_with_momentum_transition, current_recommendation)
        recommendation_with_momentum_transition._gs338_momentum_ignition_transition = True
        recommendation_with_momentum_transition._gs338_original = current_recommendation
        ui.mission_control_recommendation = recommendation_with_momentum_transition
