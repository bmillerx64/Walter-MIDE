"""GS350/GS430/GS431/GS432: keep backup downloads non-rerunning and reliable.

Streamlit's download_button reruns the app by default when clicked. In Walter,
that can look exactly like a scan refresh and can interrupt the browser download
flow for session backup exports. GS350 changes download-button interaction so
all download buttons default to on_click='ignore' unless a caller explicitly
chooses another behavior.

GS430 specialized the Flight Recorder button with a stable widget key and a
deferred payload. GS431 removed the deferred payload after live Community Cloud
validation showed it could render a clickable button without starting a browser
download. Live validation after GS431 showed the failure persisted, isolating the
remaining GS430 specialization: the forced stable key. GS432 therefore restores
the original GS350 contract completely. Download arguments and widget identity
are passed through exactly as supplied by the caller; this wrapper only prevents
a download click from rerunning the app.
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
