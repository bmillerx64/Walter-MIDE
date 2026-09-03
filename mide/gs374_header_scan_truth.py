"""GS374: make the prominent header timestamp mean last completed scan.

Walter's control header historically rendered ``BUILD.built_at`` beside the build
SHA. That value is process/deployment identity, not market-data freshness, and it
can remain unchanged for hours while AutoScan continues. On a live operator
screen that is misleading because the timestamp visually reads like scan age.

This presentation-only layer replaces that build timestamp with the authoritative
``CompletedScan.completed_at`` value already shared by every post-scan view. The
separate Market Time tile remains the live clock. Under a healthy 60-second
AutoScan, Last Scan should therefore normally trail Market Time by less than one
scan interval; if scanning stalls, the growing gap becomes immediately visible.
"""
from __future__ import annotations

import html

from .completed_scan import completed_scan_for_view
from .time_service import format_eastern_time
from .version import BUILD


def _last_scan_label(state) -> str:
    """Return an unambiguous operator-facing completed-scan timestamp."""
    scan = completed_scan_for_view(state, "header")
    if scan is None or getattr(scan, "completed_at", None) is None:
        return "Last scan: waiting"
    return f"Last scan: {format_eastern_time(scan.completed_at)}"


def _replace_build_timestamp(markup: str, label: str) -> str:
    """Swap only the historical build-time token, preserving version and SHA."""
    build_token = html.escape(str(BUILD.built_at))
    if build_token not in markup:
        return markup
    return markup.replace(build_token, html.escape(label), 1)


def install() -> None:
    """Install before app.py binds ``mission_control_header_markup``."""
    from . import ui

    current = ui.mission_control_header_markup
    if getattr(current, "_gs374_header_scan_truth", False):
        return

    original = current

    def header_with_scan_truth(*args, **kwargs) -> str:
        markup = original(*args, **kwargs)
        try:
            label = _last_scan_label(ui.st.session_state)
        except Exception:
            # Presentation must never break the dashboard. More importantly, do
            # not fall back to a deployment timestamp that can masquerade as scan
            # freshness.
            label = "Last scan: unavailable"
        return _replace_build_timestamp(markup, label)

    for name, value in getattr(original, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(header_with_scan_truth, name):
            setattr(header_with_scan_truth, name, value)
    header_with_scan_truth._gs374_header_scan_truth = True
    header_with_scan_truth._gs374_original = original
    ui.mission_control_header_markup = header_with_scan_truth
