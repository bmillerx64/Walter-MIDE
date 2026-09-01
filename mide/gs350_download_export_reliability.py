"""GS350: make download exports non-rerunning and reliable.

Streamlit's download_button reruns the app by default when clicked. In Walter,
that can look exactly like a scan refresh and can interrupt the browser download
flow for session backup exports. GS350 changes only download-button interaction:
all download buttons default to on_click='ignore' unless a caller explicitly
chooses another behavior.
"""
from __future__ import annotations


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs350_download_export_reliability", False):
        return

    def download_without_rerun(*args, **kwargs):
        kwargs.setdefault("on_click", "ignore")
        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
