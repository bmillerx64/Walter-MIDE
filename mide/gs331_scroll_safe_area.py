"""GS331: restore a safe top inset for Streamlit's app and sidebar content.

Walter's dashboard CSS historically forced the main ``.block-container`` to only
1.1rem of top padding. On current Streamlit this places the beginning of the app
under the fixed application chrome. The visible symptom is exactly what the live
browser showed: both the Radar plane and sidebar have content above the highest
reachable scroll position.

This patch does not alter container order, hide DOM, reset scroll position, or
change any scanner/trading behavior. It extends Walter's existing dashboard CSS in
place so the established single ``st.markdown`` injection contract remains intact.
"""
from __future__ import annotations


SAFE_TOP_CSS = """
<style>
/* Streamlit 1.59+ main content container. Keep the top of Walter below app chrome. */
.block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: 3.75rem !important;
}

/* Sidebar uses a separate scroll/content plane. Give it the same reachable top. */
[data-testid="stSidebarUserContent"] {
    padding-top: 3.75rem !important;
}
</style>
"""


def install() -> None:
    from . import ui

    if getattr(ui, "_gs331_scroll_safe_area_installed", False):
        return
    ui.DASHBOARD_CSS = ui.DASHBOARD_CSS + SAFE_TOP_CSS
    ui._gs331_scroll_safe_area_installed = True
