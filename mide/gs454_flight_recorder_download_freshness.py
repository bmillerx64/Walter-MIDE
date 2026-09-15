"""GS454: keep deferred Flight Recorder downloads fresh across live scans.

Live validation on 2026-09-15 showed a specific export-only failure: Walter's live
scan header kept advancing while repeated Flight Recorder downloads returned the
same older gzip snapshot. GS448 correctly deferred materialization until the
operator clicked, but the Flight Recorder button retained one stable Streamlit
widget identity. A previously materialized deferred payload could therefore remain
associated with that widget after the underlying JSONL file had grown.

GS454 changes only the Flight Recorder download widget identity. For GS448's
marked deferred callable, a cheap version key is derived from the current recorder
file identity/size/mtime. Each persisted scan therefore gives Streamlit a new
widget identity without reading or compressing the recorder during ordinary app
reruns. The expensive export remains deferred until the operator clicks. If the
file has not changed, the key remains stable. Explicit caller keys are preserved.

No scan cadence, persistence format, market-data value, discovery, VWAP,
SuperTrend, participation, expansion, scoring, ranking, qualification, alerts,
execution, or orders change.
"""
from __future__ import annotations

from pathlib import Path


AUTHORITY = "EXPORT_FRESHNESS_ONLY"
FLIGHT_RECORDER_LABEL = "Download Flight Recorder"
DEFAULT_FLIGHT_RECORDER_PATH = Path("data/flight_recorder.jsonl")
_DEFERRED_MARKER = "_gs448_deferred_flight_recorder"
_INSTALL_GENERATION = object()


def _inherit_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def recorder_version_token(path: Path = DEFAULT_FLIGHT_RECORDER_PATH) -> str:
    """Return a cheap identity token that changes whenever the recorder changes."""
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return "missing"
    return "-".join(
        str(int(value))
        for value in (
            getattr(stat, "st_dev", 0),
            getattr(stat, "st_ino", 0),
            stat.st_size,
            stat.st_mtime_ns,
        )
    )


def _argument(args: tuple, kwargs: dict, index: int, name: str):
    if name in kwargs:
        return kwargs[name]
    return args[index] if len(args) > index else None


def _has_explicit_key(args: tuple, kwargs: dict) -> bool:
    # Streamlit's signature places key after label/data/file_name/mime. App.py uses
    # keyword arguments, but preserve any explicit positional key defensively.
    return "key" in kwargs or len(args) > 4


def _install_gs455() -> None:
    from .gs455_early_ignition_3m_confirmation import install as install_gs455

    install_gs455()


def _install_gs456() -> None:
    from .gs456_canonical_30s_vwap_cross import install as install_gs456

    install_gs456()


def _install_gs457() -> None:
    from .gs457_maturation_leader_priority import install as install_gs457

    install_gs457()


def _install_gs458() -> None:
    from .gs458_flight_recorder_fragment_freshness import install as install_gs458

    install_gs458()


def install() -> None:
    """Version only GS448's deferred Flight Recorder download widget."""
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs454_install_generation", None) is _INSTALL_GENERATION:
        # Warm Streamlit sessions can already own GS454 while still needing the newer
        # discovery/operator/export refinements loaded at this same late-runtime boundary.
        _install_gs455()
        _install_gs456()
        _install_gs457()
        _install_gs458()
        return

    def download_button(*args, **kwargs):
        label = _argument(args, kwargs, 0, "label")
        data = _argument(args, kwargs, 1, "data")
        if (
            label == FLIGHT_RECORDER_LABEL
            and callable(data)
            and getattr(data, _DEFERRED_MARKER, False)
            and not _has_explicit_key(args, kwargs)
        ):
            kwargs = dict(kwargs)
            kwargs["key"] = (
                "walter-flight-recorder-"
                + recorder_version_token(DEFAULT_FLIGHT_RECORDER_PATH)
            )
        return current(*args, **kwargs)

    _inherit_markers(download_button, current)
    download_button._gs454_flight_recorder_download_freshness = True
    download_button._gs454_install_generation = _INSTALL_GENERATION
    download_button._gs454_original = current
    download_button._gs454_authority = AUTHORITY
    download_button._gs454_trading_logic_changed = False
    st.download_button = download_button

    try:
        from . import ui

        ui.st.download_button = download_button
    except Exception:
        pass
    _install_gs455()
    _install_gs456()
    _install_gs457()
    _install_gs458()
