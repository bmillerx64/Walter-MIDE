"""GS406: keep high-priority operator alerts visible across fast rescans.

Live 2026-09-09 validation showed that GS405's corrected start-to-start cadence can
leave only a short reading window after a long scan. A genuine LOOK NOW or WATCH FOR
ENTRY can therefore be recategorized by the next completed scan while the operator is
checking Webull. GS406 solves that presentation problem without pausing Walter.

Contract:
* latch only trader-visible LOOK NOW and WATCH FOR ENTRY states;
* create the latch only when a symbol newly enters one of those states;
* keep the original trigger snapshot visible for five minutes even if the current
  state later changes or the symbol drops from the visible set;
* show the symbol's current state alongside the original trigger when available;
* let autoscan, alert audio, discovery, qualification, thresholds, execution, and
  orders continue unchanged.

This module is session-local presentation state only. It does not mutate candidate
records or create any new trading authority.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import html


LATCH_TTL_SECONDS = 300
LATCH_KEY = "_gs406_operator_alert_latches"
PREVIOUS_STATE_KEY = "_gs406_operator_alert_previous_states"


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _utc(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _symbol(record: dict) -> str:
    return str(record.get("symbol") or "").strip().upper()


def _priority_states() -> tuple[str, str]:
    from . import gs310_unified_opportunity_state as unified

    return unified.WATCH_FOR_ENTRY, unified.LOOK_NOW


def _snapshot(record: dict, view: dict, triggered_at: datetime) -> dict:
    participation = _number(record, "participation_surge_score", "participation_score")
    expansion = _number(record, "expansion_quality", "expansion_score")
    return {
        "symbol": _symbol(record),
        "state": str(view.get("state") or ""),
        "triggered_at": triggered_at.astimezone(timezone.utc).isoformat(),
        "price": _number(record, "price", "last_price"),
        "vwap_distance_pct": _number(record, "vwap_distance_pct"),
        "supertrend_bullish": bool(
            record.get("supertrend_bullish") or record.get("supertrend_flip")
        ),
        "participation_score": participation,
        "expansion_score": expansion,
        "reason": str(view.get("reason") or ""),
        "next_step": str(view.get("next_step") or ""),
        "attention_provenance": list(view.get("attention_provenance") or []),
    }


def update_alert_latches(
    visible_records: list[dict],
    previous_states: dict[str, str] | None,
    latches: dict[str, dict] | None,
    *,
    now: datetime | None = None,
    state_function=None,
    ttl_seconds: int = LATCH_TTL_SECONDS,
) -> tuple[dict[str, dict], dict[str, str]]:
    """Return active latches and the current visible-state memory.

    The function is pure with respect to its inputs so regressions can exercise latch
    lifetime and transition semantics without a Streamlit session.
    """
    from . import gs310_unified_opportunity_state as unified

    state_function = state_function or unified.opportunity_state
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    previous = dict(previous_states or {})
    active = {key: deepcopy(value) for key, value in dict(latches or {}).items()}
    ttl = max(1, int(ttl_seconds))

    # Expire only the pinned presentation memory. Current cards remain governed by the
    # live opportunity-state renderer regardless of latch lifetime.
    for symbol, latch in list(active.items()):
        triggered = _utc(latch.get("triggered_at"))
        if triggered is None or (current_time - triggered).total_seconds() >= ttl:
            active.pop(symbol, None)

    high_priority = set(_priority_states())
    current_states: dict[str, str] = {}
    seen: set[str] = set()
    for record in visible_records or []:
        symbol = _symbol(record)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        view = state_function(record)
        state = str(view.get("state") or "")
        current_states[symbol] = state
        if state in high_priority and previous.get(symbol) != state:
            active[symbol] = _snapshot(record, view, current_time)

    # Keep memory only for currently visible symbols. If a symbol later leaves and
    # genuinely re-enters a high-priority state, that is a fresh operator event.
    return active, current_states


def latch_display_rows(
    latches: dict[str, dict],
    records: list[dict],
    *,
    now: datetime | None = None,
    state_function=None,
    ttl_seconds: int = LATCH_TTL_SECONDS,
) -> list[dict]:
    """Enrich pinned trigger snapshots with current live state for display only."""
    from . import gs310_unified_opportunity_state as unified

    state_function = state_function or unified.opportunity_state
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    by_symbol = {_symbol(record): record for record in records or [] if _symbol(record)}
    priority = {unified.WATCH_FOR_ENTRY: 2, unified.LOOK_NOW: 1}
    rows: list[dict] = []

    for symbol, latch in dict(latches or {}).items():
        triggered = _utc(latch.get("triggered_at"))
        if triggered is None:
            continue
        age = max(0.0, (current_time - triggered).total_seconds())
        remaining = max(0, int(ttl_seconds - age))
        if remaining <= 0:
            continue

        row = deepcopy(latch)
        current_record = by_symbol.get(symbol)
        if current_record is not None:
            current_view = state_function(current_record)
            row["current_state"] = str(current_view.get("state") or "")
            row["current_price"] = _number(current_record, "price", "last_price")
            row["current_vwap_distance_pct"] = _number(
                current_record, "vwap_distance_pct"
            )
        else:
            row["current_state"] = "NOT CURRENTLY VISIBLE"
            row["current_price"] = None
            row["current_vwap_distance_pct"] = None
        row["seconds_remaining"] = remaining
        rows.append(row)

    rows.sort(key=lambda row: str(row.get("triggered_at") or ""), reverse=True)
    rows.sort(key=lambda row: priority.get(str(row.get("state") or ""), 0), reverse=True)
    return rows


def _format_metric(label: str, value: float | None, suffix: str = "") -> str:
    if value is None:
        return ""
    return f"{html.escape(label)} {value:.1f}{html.escape(suffix)}"


def render_operator_alert_latch(
    latches: dict[str, dict], records: list[dict], *, now: datetime | None = None
) -> None:
    """Render a compact pinned alert strip above the normal Opportunity State cards."""
    from . import gs310_unified_opportunity_state as unified
    from . import ui

    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = latch_display_rows(latches, records, now=current_time)
    if not rows:
        return

    cards = []
    for row in rows:
        state = str(row.get("state") or "")
        color = unified.STATE_COLORS.get(state, "#facc15")
        remaining = int(row.get("seconds_remaining") or 0)
        minutes, seconds = divmod(remaining, 60)
        current_state = str(row.get("current_state") or "UNKNOWN")
        original_price = row.get("price")
        current_price = row.get("current_price")
        vwap_distance = row.get("vwap_distance_pct")
        participation = row.get("participation_score")
        expansion = row.get("expansion_score")

        metrics = [
            _format_metric("VWAP", vwap_distance, "%"),
            _format_metric("Participation", participation),
            _format_metric("Expansion", expansion),
        ]
        metrics = [metric for metric in metrics if metric]
        if row.get("supertrend_bullish"):
            metrics.append("1m/ST bullish")
        metric_line = " · ".join(metrics)

        original_price_text = (
            f"${float(original_price):.4f}" if original_price is not None else "n/a"
        )
        current_price_text = (
            f"${float(current_price):.4f}" if current_price is not None else "n/a"
        )
        current_note = (
            f"Current: {html.escape(current_state)} · {current_price_text}"
            if current_state
            else f"Current: unavailable · {current_price_text}"
        )
        cards.append(
            "<div style='border:1px solid {color};border-left:5px solid {color};"
            "border-radius:10px;padding:10px 14px;margin:8px 0;background:#0b1420'>"
            "<div style='font-size:12px;letter-spacing:.08em;color:{color};font-weight:800'>"
            "PINNED HIGH-PRIORITY ALERT · {minutes}:{seconds:02d} REMAINING</div>"
            "<div style='font-size:22px;font-weight:800;color:{color};margin-top:2px'>"
            "{symbol} · {state}</div>"
            "<div style='font-size:14px;color:#e5e7eb;margin-top:3px'>Triggered at {price}</div>"
            "<div style='font-size:13px;color:#cbd5e1;margin-top:3px'>{reason}</div>"
            "<div style='font-size:12px;color:#94a3b8;margin-top:4px'>{metrics}</div>"
            "<div style='font-size:13px;color:#f8fafc;margin-top:6px;font-weight:700'>"
            "{current_note}</div></div>".format(
                color=color,
                minutes=minutes,
                seconds=seconds,
                symbol=html.escape(str(row.get("symbol") or "")),
                state=html.escape(state),
                price=original_price_text,
                reason=html.escape(str(row.get("reason") or "")),
                metrics=html.escape(metric_line),
                current_note=current_note,
            )
        )

    ui.st.markdown(
        "<div style='margin:4px 0 14px 0'>"
        "<div style='font-size:13px;font-weight:800;letter-spacing:.08em;color:#f8fafc'>"
        "OPERATOR ALERT LATCH — Walter continues scanning while you verify in Webull</div>"
        + "".join(cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install as the final Opportunity State presentation wrapper after GS404."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records

    current = ui.render_escalation_engine
    if getattr(current, "_gs406_operator_alert_latch", False):
        return

    def render_with_operator_alert_latch(records: list[dict]) -> None:
        visible = ordered_escalation_records(ui.actionable_candidate_records(records))
        previous = dict(ui.st.session_state.get(PREVIOUS_STATE_KEY) or {})
        latches = dict(ui.st.session_state.get(LATCH_KEY) or {})
        now = datetime.now(timezone.utc)
        active, current_states = update_alert_latches(
            visible,
            previous,
            latches,
            now=now,
        )
        ui.st.session_state[LATCH_KEY] = active
        ui.st.session_state[PREVIOUS_STATE_KEY] = current_states
        render_operator_alert_latch(active, list(records or []) + list(visible or []), now=now)
        return current(records)

    _inherit(render_with_operator_alert_latch, current)
    render_with_operator_alert_latch._gs406_operator_alert_latch = True
    render_with_operator_alert_latch._gs406_original = current
    ui.render_escalation_engine = render_with_operator_alert_latch
