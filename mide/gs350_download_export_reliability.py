"""GS350/GS430-GS434/GS458: keep backup downloads reliable and fresh.

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

GS458 closes the freshness hole exposed after GS454. Later download wrappers such
as GS454 can live outside the original GS350 fragment. Once the fragment has been
created, fragment-only reruns otherwise call the older inner chain directly and
therefore bypass a later freshness/version wrapper. GS458 lets GS350 be safely
rebound as the final outer download boundary. Its fragment then calls the complete
current inner wrapper chain on every fragment rerun, while a private sentinel tells
the older nested GS350 instance to pass through instead of creating a second
fragment. That lets GS454 recompute the Flight Recorder version key at actual
fragment/download time.

All other download buttons retain GS350's ``on_click='ignore'`` behavior. The
Flight Recorder payload, filename, MIME type, widget identity, and any explicit
caller ``on_click`` choice are otherwise passed through unchanged.
"""
from __future__ import annotations


FLIGHT_RECORDER_LABEL = "Download Flight Recorder"
_FRAGMENT_OWNER_KWARG = "_walter_flight_recorder_fragment_owner"
_OWNER_ATTR = "_walter_gs350_download_fragment_owner"


def _button_label(args, kwargs) -> object:
    if args:
        return args[0]
    return kwargs.get("label")


def _inherit_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, _OWNER_ATTR, False):
        return

    # A late GS458 rebind intentionally wraps the already-established GS350 chain.
    # In that case the fragment must call through every newer wrapper (GS364/448/454
    # etc.) but tell the older nested GS350 instance not to create a second fragment.
    has_inner_gs350 = bool(
        getattr(current, "_gs350_download_export_reliability", False)
    )

    def download_without_rerun(*args, **kwargs):
        nested_fragment_call = bool(kwargs.pop(_FRAGMENT_OWNER_KWARG, False))
        if nested_fragment_call:
            return current(*args, **kwargs)

        if _button_label(args, kwargs) == FLIGHT_RECORDER_LABEL:
            fragment = getattr(st, "fragment", None)
            if callable(fragment):
                fragment_kwargs = dict(kwargs)
                # Let Streamlit own the normal download event, but confine its
                # rerun to this fragment instead of Walter's full application.
                fragment_kwargs.setdefault("on_click", "rerun")

                @fragment
                def flight_recorder_download_fragment():
                    call_kwargs = dict(fragment_kwargs)
                    if has_inner_gs350:
                        call_kwargs[_FRAGMENT_OWNER_KWARG] = True
                    return current(*args, **call_kwargs)

                return flight_recorder_download_fragment()

            # Defensive fallback for runtimes without fragment support.
            kwargs.setdefault("on_click", "ignore")
            return current(*args, **kwargs)

        kwargs.setdefault("on_click", "ignore")
        return current(*args, **kwargs)

    _inherit_markers(download_without_rerun, current)
    download_without_rerun._gs350_download_export_reliability = True
    download_without_rerun._gs350_original = current
    setattr(download_without_rerun, _OWNER_ATTR, True)
    st.download_button = download_without_rerun
