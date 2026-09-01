"""GS349: keep active developing setups above historical opportunity-feed noise.

Presentation-only. This does not change discovery, candidate membership, scoring,
qualification, thresholds, readiness, alerts, execution, or orders.
"""
from __future__ import annotations

import html
import re

MAX_DEVELOPING_ROWS = 4


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


def _diagnostic_number(record: dict, group: str, key: str, *fallback_keys: str, default: float | None = None) -> float | None:
    """Prefer the diagnostic map over convenience top-level fields."""
    diagnostics = record.get(group) or {}
    try:
        value = diagnostics.get(key)
        if value is not None and value != "":
            return float(value)
    except (TypeError, ValueError, AttributeError):
        pass
    return _number(record, *fallback_keys, default=default)


def _stored_trigger_check(record: dict, condition: str) -> dict | None:
    """Return the exact trigger check stored with the scanner decision, if any.

    GS358: entry-lock chips intentionally show the stored trigger snapshot rather
    than recomputing against later-enriched record fields. DEVELOPING NOW must use
    that same snapshot so the two operator surfaces cannot disagree during a live
    scan. This helper is display-only and never reevaluates qualification.
    """
    trigger = record.get("trigger_diagnostics")
    if not isinstance(trigger, dict):
        return None
    for check in trigger.get("checks") or []:
        if isinstance(check, dict) and str(check.get("condition") or "") == condition:
            return check
    return None


def _stored_trigger_number(record: dict, condition: str) -> float | None:
    """Read one observed value from Walter's stored trigger explanation.

    The current trigger contract stores human-readable reasons but not a separate
    numeric evidence payload. Parse only the stable operator phrases emitted by
    scanner_v2.trigger_diagnostics; if a phrase is absent or changes, callers fall
    back to the existing diagnostic-map path rather than inventing a value.
    """
    check = _stored_trigger_check(record, condition)
    if not check:
        return None
    reason_key = "passed_reason" if check.get("passed") else "failed_reason"
    text = str(check.get(reason_key) or "")

    if condition == "vwap":
        match = re.search(r"VWAP Distance\s*([+-]?\d+(?:\.\d+)?)%", text)
        if match:
            return float(match.group(1))
        match = re.search(r"Price\s*(\d+(?:\.\d+)?)%\s*below VWAP", text)
        if match:
            return -float(match.group(1))
        match = re.search(r"Price\s*(\d+(?:\.\d+)?)%\s*above VWAP", text)
        if match:
            return float(match.group(1))
    elif condition == "participation":
        match = re.search(r"Participation Surge\s*([+-]?\d+(?:\.\d+)?)\s*/\s*100", text)
        if match:
            return float(match.group(1))
    elif condition == "expansion_beginning":
        match = re.search(r"Expansion Quality\s*([+-]?\d+(?:\.\d+)?)\s*/\s*100", text)
        if match:
            return float(match.group(1))
    return None


def developing_records(records: list[dict]) -> list[dict]:
    from . import ui
    rows: list[dict] = []
    for title, section_rows, _expanded in ui.scanner_v2_display_sections(records or []):
        if "DEVELOPING" not in str(title).upper():
            continue
        rows.extend(section_rows)
        if len(rows) >= MAX_DEVELOPING_ROWS:
            break
    return rows[:MAX_DEVELOPING_ROWS]


def _operator_label(record: dict) -> str:
    try:
        from . import ui
        recommendation_fn = getattr(ui, "mission_control_recommendation", None)
        if callable(recommendation_fn):
            recommendation = recommendation_fn(record)
            label = str((recommendation or {}).get("label") or "").strip()
            if label:
                return label
    except Exception:
        pass
    try:
        from .gs348_st_vwap_operator_priority import active_cross
        if active_cross(str(record.get("symbol") or "")):
            return "ST/VWAP CROSS · WATCH NOW"
    except Exception:
        pass
    return "DEVELOPING"


def developing_now_markup(records: list[dict]) -> str:
    rows = developing_records(records)
    if not rows:
        return ""
    cards = []
    for record in rows:
        symbol_raw = str(record.get("symbol") or "").upper()
        symbol = html.escape(symbol_raw)
        price = _number(record, "price")
        pct = _number(record, "pct_change", "percent_change")

        # GS358: prefer the exact stored trigger snapshot used by GS353 entry
        # locks. Fall back to GS354's diagnostic-map precedence for older or
        # incomplete records that do not contain a stored trigger explanation.
        vwap = _stored_trigger_number(record, "vwap")
        if vwap is None:
            vwap = _diagnostic_number(
                record,
                "strengthening_vwap_gate",
                "distance_pct",
                "vwap_distance_pct",
                "vwap_distance",
            )
        participation = _stored_trigger_number(record, "participation")
        if participation is None:
            participation = _diagnostic_number(
                record,
                "participation_surge_diagnostics",
                "participation_score",
                "participation_surge_score",
                "participation_score",
                default=0.0,
            )
        participation = participation or 0.0
        expansion = _stored_trigger_number(record, "expansion_beginning")
        if expansion is None:
            expansion = _number(record, "expansion_quality", "expansion_score", default=0.0)
        expansion = expansion or 0.0

        supertrend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
        label = html.escape(_operator_label(record))
        price_text = f"${price:.4f}" if price is not None else "price n/a"
        pct_text = f"{pct:+.1f}%" if pct is not None else ""
        vwap_text = f"VWAP {vwap:+.1f}%" if vwap is not None else "VWAP n/a"
        st_text = "ST bullish" if supertrend else "ST not bullish"
        cards.append(
            "<div class='gs349-row'>"
            f"<div><b class='gs349-symbol'>{symbol}</b> <span class='gs349-price'>{price_text} {pct_text}</span></div>"
            f"<div class='gs349-label'>{label}</div>"
            f"<div class='gs349-evidence'>{vwap_text} · {st_text} · Participation {participation:.0f} · Expansion {expansion:.0f}</div>"
            "</div>"
        )
    return (
        "<style>"
        ".gs349-shell{background:#0b1119;border:1px solid #315076;border-left:5px solid #60a5fa;border-radius:12px;padding:11px 14px;margin:-4px 0 10px}"
        ".gs349-title{font-size:.78rem;letter-spacing:.12em;font-weight:950;color:#93c5fd;margin-bottom:5px}"
        ".gs349-sub{font-size:.82rem;color:#9fb0c4;margin-bottom:5px}"
        ".gs349-row{display:grid;grid-template-columns:minmax(150px,.85fr) minmax(185px,1fr) minmax(280px,1.8fr);gap:10px;align-items:center;border-top:1px solid #1e293b;padding:7px 0}"
        ".gs349-symbol{font-size:1rem;color:#f8fafc}.gs349-price{font-size:.8rem;color:#aeb9c7}.gs349-label{font-size:.78rem;font-weight:900;color:#60a5fa}.gs349-evidence{font-size:.82rem;color:#d7e0ea}"
        "@media(max-width:850px){.gs349-row{grid-template-columns:1fr}.gs349-label,.gs349-evidence{margin-top:-4px}}"
        "</style>"
        "<div class='gs349-shell'>"
        "<div class='gs349-title'>DEVELOPING NOW</div>"
        "<div class='gs349-sub'>Current patterns first. Historical additions/removals remain in Live Opportunity Feed below.</div>"
        + "".join(cards)
        + "</div>"
    )


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui
    current_render = ui.render_walter_mission_control
    if getattr(current_render, "_gs349_operator_first_layout", False):
        return
    def render_with_developing_first(records: list[dict]) -> None:
        result = current_render(records)
        markup = developing_now_markup(records)
        if markup:
            ui.st.markdown(markup, unsafe_allow_html=True)
        return result
    _inherit(render_with_developing_first, current_render)
    render_with_developing_first._gs349_operator_first_layout = True
    render_with_developing_first._gs349_original = current_render
    ui.render_walter_mission_control = render_with_developing_first
