"""GS336/GS337: session discipline, reset watch, and actionable evidence floor.

Presentation-only operator guidance. This module does not change discovery,
qualification, scoring, thresholds, readiness, ranking, alerts, execution, or
candidate membership. It sharpens the language Walter uses for current records
and prevents weak attention evidence from being presented as LOOK NOW.
"""
from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

EARLY_SESSION_CUTOFF = time(10, 30)
NY = ZoneInfo("America/New_York")


def _number(record: dict, key: str, default: float | None = None) -> float | None:
    try:
        value = record.get(key)
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _market_time(record: dict | None = None) -> datetime:
    record = record or {}
    for key in ("evaluated_at", "scan_time", "timestamp", "as_of"):
        value = record.get(key)
        if isinstance(value, datetime):
            return value.astimezone(NY) if value.tzinfo else value.replace(tzinfo=NY)
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed.astimezone(NY) if parsed.tzinfo else parsed.replace(tzinfo=NY)
            except ValueError:
                pass
    return datetime.now(NY)


def is_early_session(record: dict | None = None) -> bool:
    now = _market_time(record)
    return time(9, 30) <= now.time().replace(tzinfo=None) < EARLY_SESSION_CUTOFF


def _above_vwap(record: dict) -> bool:
    distance = _number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    return (distance is not None and distance >= 0.0) or relation in {
        "above",
        "above_vwap",
        "reclaimed",
    }


def _fresh_catalyst(record: dict) -> bool:
    headline = str(record.get("headline") or "").strip()
    if headline:
        return True
    for key in ("fresh_news", "news_catalyst", "has_catalyst", "catalyst_confirmed"):
        if bool(record.get(key)):
            return True
    return False


def constructive_reset(record: dict) -> bool:
    """Identify a rebuilt setup without granting entry readiness."""
    distance = _number(record, "vwap_distance_pct")
    participation = _number(record, "participation_score", 0.0) or 0.0
    expansion = _number(record, "expansion_score", 0.0) or 0.0
    supertrend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    above_vwap = _above_vwap(record)
    not_extended = distance is None or distance <= 5.0
    return bool(above_vwap and not_extended and supertrend and participation >= 55.0 and expansion >= 55.0)


def actionable_attention_floor(record: dict) -> tuple[bool, str]:
    """Require enough evidence before presentation can say LOOK NOW.

    This is intentionally a presentation guard, not a scanner/qualification gate.
    The operator rule is simple: LOOK NOW should mean interrupt and inspect, not
    merely that a chart has one or two constructive features.
    """
    if not _above_vwap(record):
        return False, "below VWAP"

    participation = _number(record, "participation_score", 0.0) or 0.0
    expansion = _number(record, "expansion_score", 0.0) or 0.0
    if participation < 35.0:
        return False, "participation is too weak"
    if expansion < 50.0:
        return False, "expansion is too weak"

    volume = _number(record, "volume", 0.0) or 0.0
    dollar_volume = _number(record, "dollar_volume", 0.0) or 0.0
    if not _fresh_catalyst(record) and volume < 250_000 and dollar_volume < 250_000:
        if participation < 55.0 or expansion < 55.0:
            return False, "no fresh catalyst and volume is still light"

    return True, "actionable attention evidence is present"


def guard_actionable_recommendation(record: dict, recommendation):
    """Downgrade weak LOOK NOW presentation without changing model state."""
    if not isinstance(recommendation, dict):
        return recommendation
    label = str(recommendation.get("label") or "").upper()
    if "LOOK NOW" not in label:
        return recommendation

    passed, reason = actionable_attention_floor(record)
    if passed:
        return recommendation

    symbol = str(record.get("symbol") or recommendation.get("symbol") or "").strip().upper()
    return {
        "symbol": symbol,
        "label": "MONITOR · EVIDENCE BUILDING",
        "message": f"Structure may be constructive, but {reason}.",
        "guidance": "Do not treat this as actionable yet. Wait for price above VWAP plus materially stronger participation and expansion; without a fresh catalyst, require real volume too.",
    }


def operator_override(record: dict) -> dict | None:
    """Return presentation guidance only; never modify trade qualification."""
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    distance = _number(record, "vwap_distance_pct")
    pct_change = _number(record, "pct_change", 0.0) or 0.0

    if is_early_session(record):
        if constructive_reset(record):
            return {
                "symbol": symbol,
                "label": "EARLY SESSION · LOOK NOW",
                "message": "Constructive rebuild is forming, but early-session risk remains elevated.",
                "guidance": "Open the chart. Require the normal Walter entry evidence before acting; do not waive any gate because of momentum.",
            }
        if pct_change >= 50.0 or (distance is not None and distance > 5.0):
            return {
                "symbol": symbol,
                "label": "EARLY SESSION · RESET REQUIRED",
                "message": "Strong mover, but the first hour remains prone to extension, halts, and failed continuation.",
                "guidance": "Watch only. Wait for a constructive reset, VWAP relationship, SuperTrend support, and renewed participation before reconsidering.",
            }

    if constructive_reset(record):
        return {
            "symbol": symbol,
            "label": "SECOND ENTRY FORMING",
            "message": "Price structure has rebuilt after the initial move.",
            "guidance": "Open the chart and confirm the normal Walter gates. This is a reset/re-entry watch, not an automatic entry signal.",
        }
    return None


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    current = ui.render_walter_mission_control
    if getattr(current, "_gs336_early_session_reset_watch", False):
        return

    def render_with_session_discipline(records: list[dict]) -> None:
        if records:
            prioritized = []
            ordinary = []
            for record in records:
                override = operator_override(record)
                if override is not None:
                    copy = dict(record)
                    copy["_gs336_operator_override"] = override
                    prioritized.append(copy)
                else:
                    ordinary.append(record)
            records = prioritized + ordinary
        return current(records)

    _inherit_wrapper_contract(render_with_session_discipline, current)
    render_with_session_discipline._gs336_early_session_reset_watch = True
    render_with_session_discipline._gs336_original = current
    ui.render_walter_mission_control = render_with_session_discipline

    current_recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(current_recommendation) and not getattr(current_recommendation, "_gs336_early_session_reset_watch", False):
        def recommendation_with_session_discipline(record: dict):
            override = record.get("_gs336_operator_override") if isinstance(record, dict) else None
            if isinstance(override, dict):
                recommendation = override
            else:
                recommendation = current_recommendation(record)
            return guard_actionable_recommendation(record, recommendation)

        _inherit_wrapper_contract(recommendation_with_session_discipline, current_recommendation)
        recommendation_with_session_discipline._gs336_early_session_reset_watch = True
        recommendation_with_session_discipline._gs336_original = current_recommendation
        ui.mission_control_recommendation = recommendation_with_session_discipline
