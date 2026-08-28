"""GS327: keep trader results above verification plumbing on the Radar view.

Walter's trust, architecture, and market-quality panels were invaluable while the
live pipeline was being verified. They are diagnostic/protective evidence, not
trading results. This presentation-only layer removes those large always-visible
panels from the top of Radar and replaces the verbose mission header with a compact
flight-deck status strip. Detailed health, accounting, verification, and audit data
remain available in System Status, Diagnostics, and the Flight Recorder.

No scanner membership, thresholds, scoring, qualification, ranking, readiness,
alerts, execution, news, or persistence behavior is changed here.
"""
from __future__ import annotations

import html


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
        "<div><b>🛰️ Walter · MIDE Radar</b> "
        f"<span class='small'>{status_dot} {status} · {phase} · {market_time}</span></div>"
        "<div class='small' style='font-weight:800'>"
        f"{symbols} scanned · {candidates} candidates · {focus} focus · "
        f"{escalating} escalating · Auto {auto_scan}</div>"
        "</div></div>"
    )


def install() -> None:
    """Install a presentation-only pilot view before app.py imports UI symbols."""
    from . import ui

    if getattr(ui.mission_control_header_markup, "_gs327_pilot_view", False):
        return

    original_header = ui.mission_control_header_markup
    original_integrity = ui.data_integrity_markup
    original_market = ui.market_session_quality_markup

    compact_mission_header_markup._gs327_pilot_view = True
    compact_mission_header_markup._gs327_original = original_header
    ui.mission_control_header_markup = compact_mission_header_markup

    def hidden_scan_trust(*_args, **_kwargs) -> str:
        # Full trust/verification evidence remains in lower diagnostics surfaces.
        return ""

    hidden_scan_trust._gs327_pilot_view = True
    hidden_scan_trust._gs327_original = original_integrity
    ui.data_integrity_markup = hidden_scan_trust

    def hidden_market_quality(*_args, **_kwargs) -> str:
        # Market-quality detail remains diagnostic context rather than windshield UI.
        return ""

    hidden_market_quality._gs327_pilot_view = True
    hidden_market_quality._gs327_original = original_market
    ui.market_session_quality_markup = hidden_market_quality
