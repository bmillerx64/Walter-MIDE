"""GS350/GS430: make download exports non-rerunning and reliable.

Streamlit's download_button reruns the app by default when clicked. In Walter,
that can look exactly like a scan refresh and can interrupt the browser download
flow for session backup exports. GS350 changes download-button interaction so
all download buttons default to on_click='ignore' unless a caller explicitly
chooses another behavior.

GS430 additionally stabilizes the sidebar Flight Recorder export. That button is
recreated around Walter's scan orchestration, and its payload is large enough
that eagerly registering a new in-memory download on every rerun can race the
frontend and queue clicks until a later refresh. For that one established label,
use a stable widget key and hand Streamlit a deferred callable. The bytes passed
by the existing app are preserved exactly; only their registration/download
lifecycle changes.
"""
from __future__ import annotations


FLIGHT_RECORDER_LABEL = "Download Flight Recorder"
FLIGHT_RECORDER_KEY = "walter_flight_recorder_download"


def _deferred(value):
    """Return Streamlit-compatible deferred data without changing the payload."""
    if callable(value):
        return value
    return lambda value=value: value


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs350_download_export_reliability", False):
        return

    def download_without_rerun(*args, **kwargs):
        kwargs.setdefault("on_click", "ignore")

        label = kwargs.get("label", args[0] if args else None)
        if label == FLIGHT_RECORDER_LABEL:
            kwargs.setdefault("key", FLIGHT_RECORDER_KEY)
            if "data" in kwargs:
                kwargs["data"] = _deferred(kwargs["data"])
            elif len(args) > 1:
                mutable_args = list(args)
                mutable_args[1] = _deferred(mutable_args[1])
                args = tuple(mutable_args)

        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
