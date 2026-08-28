"""GS327/GS328: compact Radar pilot view without hidden diagnostic DOM.

The Radar view is for operating Walter, not for replaying the verification path.
In a real Streamlit run this presentation-only layer keeps a compact operator
header visible and suppresses the large Scan Trust and market-quality panels.
Outside Streamlit runtime (including direct unit-test calls), the established
renderers remain unchanged so their diagnostic contracts stay independently tested.

No scanner membership, thresholds, scoring, qualification, ranking, readiness,
alerts, execution, news, or persistence behavior is changed here.
"""
from __future__ import annotations

import html


def _in_streamlit_run() -> bool:
    """True only while Streamlit is executing an application script."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def compact_mission_header_markup(*_args, **kwargs) -> str:
    """Render only operator-relevant scan state; omit funnel/accounting detail."""
    live = bool(kwargs.get("live"))
    status = "LIVE" if live else "DEMO"
    status_dot = "🟢" if live else "⚪"
    phase = html.escape(str(kwargs.get("market_phase") or "Unknown"))
    market_time = html.escape(str(kwargs.get("market_time") or ""))
    symbols = int(kwargs.get("symbols_sampled") or 0)
    candidates = int(kwargs.get("candidate_count") or 0)
    focus = int(kwargs.get("focus_count") or 0)
    escalating = int(kwargs.get("escalation_count") or 0)
    auto_scan = html.escape(str(kwargs.get("auto_scan") or "Disabled"))
    return (
        "<div class='mide-card' style='padding:10px 14px;margin-bottom:8px'>"
        "<div style='display:flex;align-items:center;justify-content:space-between;"
        "gap:12px;flex-wrap:wrap'>"
        "<div><b>🛰️ Walter • MIDE Radar</b> "
        f"<span class='small'>{status_dot} {status} · {phase} · {market_time}</span></div>"
        "<div class='small' style='font-weight:800'>"
        f"{symbols} scanned · {candidates} candidates · {focus} focus · "
        f"{escalating} escalating · Auto {auto_scan}</div>"
        "</div></div>"
    )


def install() -> None:
    """Install compact live presentation while preserving direct renderer contracts."""
    from . import ui

    if getattr(ui.mission_control_header_markup, "_gs328_scroll_repair", False):
        return

    original_header = getattr(
        ui.mission_control_header_markup,
        "_gs327_original",
        ui.mission_control_header_markup,
    )
    original_integrity = getattr(
        ui.data_integrity_markup,
        "_gs327_original",
        ui.data_integrity_markup,
    )
    original_market = getattr(
        ui.market_session_quality_markup,
        "_gs327_original",
        ui.market_session_quality_markup,
    )

    def pilot_header(*args, **kwargs) -> str:
        if not _in_streamlit_run():
            return original_header(*args, **kwargs)
        return compact_mission_header_markup(*args, **kwargs)

    pilot_header._gs327_pilot_view = True
    pilot_header._gs328_scroll_repair = True
    pilot_header._gs327_original = original_header
    ui.mission_control_header_markup = pilot_header

    def suppressed_scan_trust(*args, **kwargs) -> str:
        if not _in_streamlit_run():
            return original_integrity(*args, **kwargs)
        return ""

    suppressed_scan_trust._gs327_pilot_view = True
    suppressed_scan_trust._gs328_scroll_repair = True
    suppressed_scan_trust._gs327_original = original_integrity
    ui.data_integrity_markup = suppressed_scan_trust

    def suppressed_market_quality(*args, **kwargs) -> str:
        if not _in_streamlit_run():
            return original_market(*args, **kwargs)
        return ""

    suppressed_market_quality._gs327_pilot_view = True
    suppressed_market_quality._gs328_scroll_repair = True
    suppressed_market_quality._gs327_original = original_market
    ui.market_session_quality_markup = suppressed_market_quality
