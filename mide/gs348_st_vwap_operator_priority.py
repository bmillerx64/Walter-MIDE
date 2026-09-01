"""GS348: elevate fresh SuperTrend/VWAP crosses and suppress low-volume developing noise.

Presentation/alert priority only. This module does not change discovery membership,
qualification, scoring, readiness, execution, orders, or trade rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

MIN_ABSOLUTE_VOLUME = 250_000.0
MIN_VOLUME_ACCELERATION = 1.2
MIN_PARTICIPATION = 20.0
MIN_EXPANSION = 40.0
EVENT_TTL_SECONDS = 95.0


@dataclass(frozen=True)
class STVWAPSnapshot:
    supertrend_value: float
    vwap_value: float
    seen_at: float


_previous: dict[str, STVWAPSnapshot] = {}
_active_crosses: dict[str, float] = {}


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


def _fresh_catalyst(record: dict) -> bool:
    return bool(
        str(record.get("headline") or "").strip()
        or record.get("fresh_news")
        or record.get("news_catalyst")
        or record.get("has_catalyst")
        or record.get("catalyst_confirmed")
    )


def _price_above_vwap(record: dict) -> bool:
    price = _number(record, "price")
    vwap = _number(record, "vwap_value")
    if price is not None and vwap is not None:
        return price >= vwap
    distance = _number(record, "vwap_distance_pct", "vwap_distance")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    return (distance is not None and distance >= 0) or relation in {"above", "above_vwap", "reclaimed", "pass"}


def _supporting_evidence(record: dict) -> bool:
    volume = _number(record, "volume", default=0.0) or 0.0
    if volume < MIN_ABSOLUTE_VOLUME and not _fresh_catalyst(record):
        return False
    volume_accel = _number(record, "volume_acceleration", default=0.0) or 0.0
    participation = _number(record, "participation_score", "participation_surge_score", default=0.0) or 0.0
    expansion = _number(record, "expansion_score", "expansion_quality", default=0.0) or 0.0
    return (
        volume_accel >= MIN_VOLUME_ACCELERATION
        or participation >= MIN_PARTICIPATION
        or expansion >= MIN_EXPANSION
        or _fresh_catalyst(record)
    )


def st_vwap_cross(record: dict, prior: STVWAPSnapshot | None) -> tuple[bool, str]:
    """Detect a fresh bullish SuperTrend line cross above VWAP."""
    st_value = _number(record, "supertrend_value")
    vwap_value = _number(record, "vwap_value")
    if prior is None or st_value is None or vwap_value is None:
        return False, "insufficient line history"
    if not (prior.supertrend_value < prior.vwap_value and st_value >= vwap_value):
        return False, "no fresh ST/VWAP cross"
    if not bool(record.get("supertrend_bullish") or record.get("supertrend_flip")):
        return False, "SuperTrend not bullish"
    if not _price_above_vwap(record):
        return False, "price not above VWAP"
    if not _supporting_evidence(record):
        return False, "insufficient supporting volume/evidence"
    return True, "SuperTrend crossed above VWAP with supporting evidence"


def observe_crosses(records: list[dict], *, now: float | None = None) -> list[str]:
    now = monotonic() if now is None else now
    crossed: list[str] = []
    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        st_value = _number(record, "supertrend_value")
        vwap_value = _number(record, "vwap_value")
        if not symbol or st_value is None or vwap_value is None:
            continue
        prior = _previous.get(symbol)
        ok, _reason = st_vwap_cross(record, prior)
        if ok:
            _active_crosses[symbol] = now
            crossed.append(symbol)
        _previous[symbol] = STVWAPSnapshot(st_value, vwap_value, now)
    expired = [symbol for symbol, stamp in _active_crosses.items() if now - stamp > EVENT_TTL_SECONDS]
    for symbol in expired:
        _active_crosses.pop(symbol, None)
    return crossed


def active_cross(symbol: str, *, now: float | None = None) -> bool:
    now = monotonic() if now is None else now
    stamp = _active_crosses.get(str(symbol or "").strip().upper())
    return stamp is not None and now - stamp <= EVENT_TTL_SECONDS


def operator_relevant_developing(record: dict) -> bool:
    """Keep low-volume DEVELOPING names from occupying scarce operator attention."""
    symbol = str(record.get("symbol") or "").strip().upper()
    if active_cross(symbol):
        return True
    volume = _number(record, "volume", default=0.0) or 0.0
    return volume >= MIN_ABSOLUTE_VOLUME or _fresh_catalyst(record)


def reset_state() -> None:
    _previous.clear()
    _active_crosses.clear()


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import escalation, ui

    if getattr(escalation.escalation_state_changes, "_gs348_st_vwap_operator_priority", False):
        return

    original_changes = escalation.escalation_state_changes
    original_phrase = escalation.escalation_alert_phrase

    def state_changes_with_cross(records: list[dict]) -> list[dict]:
        observe_crosses(records)
        changes = list(original_changes(records))
        existing = {str(item.get("symbol") or "").upper() for item in changes}
        for record in records or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if symbol and active_cross(symbol) and symbol not in existing:
                changes.insert(0, {"symbol": symbol, "from": "ST BELOW VWAP", "to": "ST/VWAP CROSS"})
                existing.add(symbol)
        return changes

    def alert_phrase_with_cross(records: list[dict]) -> str:
        changes = state_changes_with_cross(records)
        cross = next((item for item in changes if item.get("to") == "ST/VWAP CROSS"), None)
        if cross:
            return (
                f"{cross['symbol']} SuperTrend crossed above VWAP. Watch now. "
                "Confirm volume, participation, and expansion before entry."
            )
        return original_phrase(records)

    _inherit(state_changes_with_cross, original_changes)
    _inherit(alert_phrase_with_cross, original_phrase)
    state_changes_with_cross._gs348_st_vwap_operator_priority = True
    alert_phrase_with_cross._gs348_st_vwap_operator_priority = True
    escalation.escalation_state_changes = state_changes_with_cross
    escalation.escalation_alert_phrase = alert_phrase_with_cross

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation):
        def recommendation_with_cross(record: dict):
            base = current_recommendation(record)
            symbol = str(record.get("symbol") or "").strip().upper()
            if not active_cross(symbol):
                return base
            base_label = str(base.get("label") or "").upper() if isinstance(base, dict) else ""
            stronger = ("MOMENTUM IGNITING", "LOOK NOW", "WATCH FOR ENTRY", "ENTRY", "CHASE", "RESET REQUIRED")
            if any(token in base_label for token in stronger):
                return base
            return {
                "symbol": symbol,
                "label": "ST/VWAP CROSS · WATCH NOW",
                "message": "SuperTrend has crossed above VWAP while price/trend structure remains constructive.",
                "guidance": "Open the chart now. This is not an entry call; confirm volume, participation, expansion, and VWAP hold before acting.",
            }
        _inherit(recommendation_with_cross, current_recommendation)
        recommendation_with_cross._gs348_st_vwap_operator_priority = True
        ui.mission_control_recommendation = recommendation_with_cross

    current_sections = ui.scanner_v2_display_sections
    def sections_without_thin_developing(records: list[dict]):
        sections = current_sections(records)
        cleaned = []
        for title, rows, expanded in sections:
            if "DEVELOPING" in str(title).upper():
                rows = [row for row in rows if operator_relevant_developing(row)]
            cleaned.append((title, rows, expanded))
        return cleaned
    _inherit(sections_without_thin_developing, current_sections)
    sections_without_thin_developing._gs348_st_vwap_operator_priority = True
    ui.scanner_v2_display_sections = sections_without_thin_developing
