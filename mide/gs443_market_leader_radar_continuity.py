"""GS443: keep an unfocused current market leader visible without granting entry.

Sep. 11 live validation exposed a narrow sightline gap. A current Webull top mover can
be one of the session's true leaders while temporary countertrend/weak structure keeps
it out of Primary/Secondary Mission and GS305's structure-aware attention lane. That is
correct for entry discipline, but it should not make the leader disappear from the
operator's radar while Walter waits for a reset or 30s -> 1m -> 3m maturation.

GS443 reuses established thresholds rather than creating a new qualification family:
* +20% is GS305's existing major-mover threshold;
* $250k dollar volume is GS305's existing attention-liquidity floor;
* 78 market-dominance is already used by attention ranking as exceptional-leader
  evidence when combined with the stricter attention/participation gates.

The continuity strip is presentation-only and intentionally fills only the gap left by
existing lanes. It excludes symbols already in Mission, already eligible for GS305
attention, and 75%+ extreme movers already owned by GS333. It never plays audio,
changes scores, manufactures LOOK NOW / ENTRY READY semantics, or alters discovery,
qualification, readiness, thresholds, execution, or orders.
"""
from __future__ import annotations

import html
from collections.abc import Iterable


MAJOR_MOVER_PCT = 20.0
MIN_DOLLAR_VOLUME = 250_000.0
LEADER_DOMINANCE = 78.0
EXTREME_MOVER_PCT = 75.0


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _focused_symbols(mission: dict | None) -> set[str]:
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
    """Return one uncovered current leader plus display evidence, without mutation."""
    from .gs305_second_wave_attention import attention_evaluation
    from .gs309_current_attention_mission import current_attention_provenance

    focused = _focused_symbols(mission)
    choices: list[tuple[tuple[float, float, float], dict, dict]] = []

    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in focused:
            continue

        # This lane is for current session leaders, not stale ledger names or pure
        # news seeds. GS309's DAY_GAINERS provenance is the existing current-mover
        # authority used by live Mission selection.
        provenance = tuple(current_attention_provenance(record))
        if "WEBULL_TOP_MOVER" not in provenance:
            continue

        pct_change = _number(record, "pct_change", default=0.0) or 0.0
        dollar_volume = _number(record, "dollar_volume", default=0.0) or 0.0
        dominance = _number(record, "market_dominance_score", default=0.0) or 0.0
        if pct_change < MAJOR_MOVER_PCT:
            continue
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        if dominance < LEADER_DOMINANCE:
            continue

        # GS333 already owns extraordinary 75%+ current movers at the operator
        # sightline. Do not create a second panel for the same event.
        if pct_change >= EXTREME_MOVER_PCT:
            continue

        # GS305 already supplies a structure-aware early-attention lane. GS443 is
        # deliberately the continuity fallback when that lane says structure is not
        # currently worthy of elevation.
        existing_attention = attention_evaluation(record)
        if existing_attention.get("eligible"):
            continue

        distance = _number(record, "vwap_distance_pct")
        relation = str(record.get("vwap_relation") or "").strip().lower()
        alignment = int(_number(record, "alignment_score", default=0.0) or 0)

        if distance is not None and distance > 5.0:
            state = "WAIT FOR RESET"
            guidance = (
                "Dominant current mover, but extended above VWAP. Keep the chart available; "
                "do not chase. Reassess only after a constructive reset."
            )
        elif relation != "above" or alignment < 2:
            state = "STRUCTURE NOT READY"
            guidance = (
                "Dominant current mover with incomplete structure. Keep it on radar while "
                "30s → 1m → 3m alignment develops; normal qualification remains closed."
            )
        else:
            state = "TRACK RE-IGNITION"
            guidance = (
                "Dominant current mover returning toward workable structure. Keep it visible; "
                "normal qualification still decides whether any trade is justified."
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
    """Render a compact watch-only continuity strip below actionable Mission output."""
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


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Append one uncovered leader strip after existing Mission/action presentation."""
    from . import ui

    current = ui.render_walter_mission_control
    if getattr(current, "_gs443_market_leader_radar_continuity", False):
        return

    def render_walter_mission_control(records: list[dict]) -> None:
        # Preserve action-first ordering: current WATCH/ENTRY/extreme/near-miss output
        # renders before this watch-only continuity strip.
        result = current(records)
        if not _in_streamlit_run():
            return result
        mission = ui.walter_mission_control(records)
        _record, event = market_leader_candidate(records, mission=mission)
        if event is not None:
            ui.st.markdown(market_leader_markup(event), unsafe_allow_html=True)
        return result

    _inherit(render_walter_mission_control, current)
    render_walter_mission_control._gs443_market_leader_radar_continuity = True
    render_walter_mission_control._gs443_original = current
    ui.render_walter_mission_control = render_walter_mission_control
