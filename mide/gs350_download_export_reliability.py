"""GS350/GS430/GS431/GS432/GS433/GS434: keep backup downloads reliable.

GS350 made ordinary download buttons frontend-only with ``on_click='ignore'`` so
clicking a backup would not trigger Walter's full application rerun. GS430-GS432
then tested and removed two Flight Recorder-specific experiments (deferred data
and a forced stable widget key) after live Community Cloud evidence showed the
button could visibly activate without starting a browser download.

GS433 restored the Flight Recorder's native ``on_click='rerun'`` lifecycle, but
live validation on the merged GS433 runtime still left the export vulnerable to
Walter's full-app rerun path. GS434 confines only the Flight Recorder button to a
Streamlit fragment. The button keeps native rerun semantics, but the rerun is
owned by that small fragment instead of Walter's full application.

All other download buttons retain GS350's ``on_click='ignore'`` behavior. The
Flight Recorder payload, filename, MIME type, widget identity, and any explicit
caller ``on_click`` choice are otherwise passed through unchanged.
"""
from __future__ import annotations


FLIGHT_RECORDER_LABEL = "Download Flight Recorder"


def _button_label(args, kwargs) -> object:
    if args:
        return args[0]
    return kwargs.get("label")


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs350_download_export_reliability", False):
        return

    def download_without_rerun(*args, **kwargs):
        if _button_label(args, kwargs) == FLIGHT_RECORDER_LABEL:
            fragment = getattr(st, "fragment", None)
            if callable(fragment):
                fragment_kwargs = dict(kwargs)
                # Let Streamlit own the normal download event, but confine its
                # rerun to this fragment instead of Walter's full application.
                fragment_kwargs.setdefault("on_click", "rerun")

                @fragment
                def flight_recorder_download_fragment():
                    return current(*args, **fragment_kwargs)

                return flight_recorder_download_fragment()

            # Defensive fallback for runtimes without fragment support.
            kwargs.setdefault("on_click", "ignore")
            return current(*args, **kwargs)

        kwargs.setdefault("on_click", "ignore")
        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
