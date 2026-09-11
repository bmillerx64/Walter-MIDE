"""GS350/GS430/GS431: keep backup downloads non-rerunning and reliable.

Streamlit's download_button reruns the app by default when clicked. In Walter,
that can look exactly like a scan refresh and can interrupt the browser download
flow for session backup exports. GS350 changes download-button interaction so
all download buttons default to on_click='ignore' unless a caller explicitly
chooses another behavior.

GS430 added a stable widget key for the sidebar Flight Recorder export and also
wrapped its bytes in a deferred callable. Live validation on Streamlit Community
Cloud showed the callable path could render an active button but produce no
browser download, even after refresh. GS431 keeps the useful stable key while
restoring the proven direct payload behavior. No download payload is modified.
"""
from __future__ import annotations


FLIGHT_RECORDER_LABEL = "Download Flight Recorder"
FLIGHT_RECORDER_KEY = "walter_flight_recorder_download"


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs350_download_export_reliability", False):
        return

    def download_without_rerun(*args, **kwargs):
        kwargs.setdefault("on_click", "ignore")

        label = kwargs.get("label", args[0] if args else None)
        if label == FLIGHT_RECORDER_LABEL:
            # Preserve one identity across autoscan reruns, but pass the data
            # through exactly as supplied. Production proved that deferred
            # callables could leave this large export visually clickable yet
            # fail to start a browser download.
            kwargs.setdefault("key", FLIGHT_RECORDER_KEY)

        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
