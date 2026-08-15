"""GS259: remove obsolete Alpaca feed badges from Walter's Webull-only UI.

GS258 hard-cut selectable live mode to Webull.  app.py still contains two legacy
Alpaca-feed status calls in the sidebar.  Until that large module is decomposed,
this narrow runtime shim suppresses only those exact obsolete messages.  It does
not alter market data, scan logic, settings, scoring, ranking, or alerts.
"""
from __future__ import annotations


LEGACY_SUCCESS_MESSAGES = {"SIP feed selected"}
LEGACY_WARNING_PREFIXES = (
    "IEX feed selected. Set ALPACA_FEED=",
)


def install() -> None:
    import streamlit as st

    if getattr(st.success, "_gs259_alpaca_ui_cleanup", False):
        return

    original_success = st.success
    original_warning = st.warning

    def success(body, *args, **kwargs):
        if str(body).strip() in LEGACY_SUCCESS_MESSAGES:
            return None
        return original_success(body, *args, **kwargs)

    def warning(body, *args, **kwargs):
        text = str(body).strip()
        if any(text.startswith(prefix) for prefix in LEGACY_WARNING_PREFIXES):
            return None
        return original_warning(body, *args, **kwargs)

    success._gs259_alpaca_ui_cleanup = True
    warning._gs259_alpaca_ui_cleanup = True
    st.success = success
    st.warning = warning
