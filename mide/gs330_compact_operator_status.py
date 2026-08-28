"""GS330: compress verification surfaces without removing Streamlit elements.

GS327/328 proved that deleting or hiding top-of-page Streamlit output can disturb
browser scroll anchoring. GS330 takes the conservative path: every existing top
slot remains present and visibly rendered, but the three verification/status
surfaces are reduced to thin operator ribbons during a live Streamlit run.

Outside Streamlit runtime the established renderer contracts remain unchanged for
unit tests and offline diagnostics. No scanner membership, thresholds, scoring,
qualification, ranking, readiness, alerts, execution, news, or persistence logic
is changed.
"""
from __future__ import annotations

import html


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def compact_header_markup(*_args, **kwargs) -> str:
    live = bool(kwargs.get("live"))
    status = "🟢 LIVE" if live else "🟡 DEMO"
    phase = html.escape(str(kwargs.get("market_phase") or "Unknown"))
    market_time = html.escape(str(kwargs.get("market_time") or ""))
    symbols = int(kwargs.get("symbols_sampled") or 0)
    prefiltered = int(kwargs.get("prefilter_count") or 0)
    candidates = int(kwargs.get("candidate_count") or 0)
    focus = int(kwargs.get("focus_count") or 0)
    escalating = int(kwargs.get("escalation_count") or 0)
    auto_scan = html.escape(str(kwargs.get("auto_scan") or "Disabled"))
    return (
        "<div class='mide-card' style='padding:8px 12px;margin:2px 0 6px'>"
        "<div style='display:flex;justify-content:space-between;gap:12px;"
        "align-items:center;flex-wrap:wrap'>"
        f"<b>🛰 Walter · {status} · {phase} · {market_time}</b>"
        "<span class='small' style='font-weight:800'>"
        f"{symbols} scanned · {prefiltered} prefiltered · {candidates} candidates · "
        f"{focus} focus · {escalating} escalating · Auto {auto_scan}</span>"
        "</div></div>"
    )


def compact_integrity_markup(report: dict) -> str:
    status = str(report.get("status") or "AWAITING SCAN")
    trust = report.get("trust_score")
    integrity = report.get("record_integrity_pct")
    freshness = report.get("freshness_pct")
    unique = int(report.get("unique_symbols", 0) or 0)
    records = int(report.get("record_count", 0) or 0)
    icon = {
        "HEALTHY SCAN": "🟢",
        "VALID EMPTY PASS": "🔵",
        "DEGRADED DATA": "🟠",
        "PROVIDER / PIPELINE FAILURE": "🔴",
    }.get(status, "⚪")

    def pct(value) -> str:
        try:
            return f"{float(value):.0f}%"
        except (TypeError, ValueError):
            return "N/A"

    return (
        "<div class='mide-card small' style='padding:6px 12px;margin:0 0 6px'>"
        f"<b>{icon} Scan trust: {html.escape(status)} · {pct(trust)}</b>"
        f" &nbsp; Integrity {pct(integrity)} · Freshness {pct(freshness)} · "
        f"Records {unique}/{records}"
        "</div>"
    )


def compact_market_markup(records: list[dict], *, snapshot_metrics: dict | None = None) -> str:
    from . import ui

    session = ui.market_session_quality(records, snapshot_metrics=snapshot_metrics)
    mode = html.escape(str(session.get("mode") or "Market"))
    confidence = int(session.get("confidence") or 0)
    guidance = html.escape(str(session.get("guidance") or ""))
    if session.get("snapshot_based") and snapshot_metrics:
        detail = (
            f"{int(snapshot_metrics.get('symbol_count', 0) or 0)} scanned · "
            f"avg move {float(snapshot_metrics.get('avg_pct_change', 0) or 0):.1f}%"
        )
    else:
        detail = (
            f"{int(session.get('qualified') or 0)} qualified · "
            f"{int(session.get('entry_ready') or 0)} entry ready · "
            f"participation {int(session.get('average_participation') or 0)}% · "
            f"expansion {int(session.get('average_expansion') or 0)}%"
        )
    return (
        "<div class='mide-card' style='padding:7px 12px;margin:0 0 6px'>"
        "<div style='display:flex;justify-content:space-between;gap:12px;"
        "align-items:center;flex-wrap:wrap'>"
        f"<b>{mode} · confidence {confidence}%</b>"
        f"<span class='small'>{html.escape(detail)} · {guidance}</span>"
        "</div></div>"
    )


def install() -> None:
    from . import ui

    if getattr(ui.mission_control_header_markup, "_gs330_compact_status", False):
        return

    original_header = ui.mission_control_header_markup
    original_integrity = ui.data_integrity_markup
    original_market = ui.market_session_quality_markup

    def header(*args, **kwargs):
        if _in_streamlit_run():
            return compact_header_markup(*args, **kwargs)
        return original_header(*args, **kwargs)

    def integrity(*args, **kwargs):
        if _in_streamlit_run():
            return compact_integrity_markup(*args, **kwargs)
        return original_integrity(*args, **kwargs)

    def market(*args, **kwargs):
        if _in_streamlit_run():
            return compact_market_markup(*args, **kwargs)
        return original_market(*args, **kwargs)

    for wrapper, original in (
        (header, original_header),
        (integrity, original_integrity),
        (market, original_market),
    ):
        wrapper._gs330_compact_status = True
        wrapper._gs330_original = original

    ui.mission_control_header_markup = header
    ui.data_integrity_markup = integrity
    ui.market_session_quality_markup = market
