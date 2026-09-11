"""GS350/GS430/GS431/GS432/GS433: keep backup downloads reliable.

Streamlit's download_button reruns the app by default when clicked. In Walter,
that can look exactly like a scan refresh and can interrupt browser download
flow for ordinary session backup exports. GS350 therefore made download buttons
default to on_click='ignore' unless a caller explicitly chose another behavior.

GS430 specialized the Flight Recorder button with a stable widget key and a
deferred payload. GS431 removed the deferred payload, and GS432 removed the
forced key after live Community Cloud validation showed the download still did
not start.

Live validation on the fully current GS432 runtime then proved the Flight
Recorder button could still visibly activate without producing a browser
download, even while Walter was idle. That rules out both GS430 specializations
and isolates the remaining Flight Recorder-specific departure from Streamlit's
native lifecycle: GS350's forced on_click='ignore'.

GS433 therefore lets only the Flight Recorder use Streamlit's native rerun click
contract. Candidate History and all other downloads keep GS350's non-rerunning
behavior. Payloads, widget identity, file metadata, scan logic, and recorder
contents are untouched.
"""
from __future__ import annotations


FLIGHT_RECORDER_LABEL = "Download Flight Recorder"


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs350_download_export_reliability", False):
        return

    def download_without_rerun(*args, **kwargs):
        label = args[0] if args else kwargs.get("label")
        if label == FLIGHT_RECORDER_LABEL:
            # Do not force GS350's no-rerun transport onto the Flight Recorder.
            # Streamlit's native click/rerun lifecycle has the browser media
            # handoff semantics that Community Cloud live validation requires.
            kwargs.setdefault("on_click", "rerun")
        else:
            kwargs.setdefault("on_click", "ignore")
        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
