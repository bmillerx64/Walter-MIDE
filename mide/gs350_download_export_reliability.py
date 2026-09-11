"""GS350/GS430/GS431/GS432/GS433: keep backup downloads reliable.

GS350 made ordinary download buttons frontend-only with ``on_click='ignore'`` so
clicking a backup would not trigger Walter's full application rerun. GS430-GS432
then tested and removed two Flight Recorder-specific experiments (deferred data
and a forced stable widget key) after live Community Cloud evidence showed the
button could visibly activate without starting a browser download.

GS433 changes only the Flight Recorder interaction boundary. Current Streamlit
recommends placing a download button inside ``st.fragment`` when a download must
not rerun the full application. Walter's Flight Recorder now follows that native
path: the button uses normal ``on_click='rerun'`` semantics *inside a fragment*,
so the click/download lifecycle is owned by that small fragment rather than by a
frontend-only widget competing with Walter's timed full-app AutoScan reruns.

All other download buttons retain the GS350 ``on_click='ignore'`` behavior. The
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

        kwargs.setdefault("on_click", "ignore")
        return current(*args, **kwargs)

    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    st.download_button = download_without_rerun
