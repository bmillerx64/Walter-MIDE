"""GS448: remove Flight Recorder backup bytes from every full-app rerun.

Live evidence on 2026-09-11 exposed an independent Community Cloud memory failure.
The downloaded Flight Recorder was already ~82 MiB raw / ~5.9 MiB gzip. Even after
GS446 deferred Candidate History, ``app.py`` still rendered Download Flight Recorder
with eager bytes after each scan. Streamlit documents that direct download data is
stored in memory while the user remains connected, so an append-only recorder produces
one new large in-memory payload every recurring rerun.

GS448 changes only the default live Flight Recorder export surface. On render,
``FlightRecorder.export_bytes()`` returns a zero-argument callable. Streamlit therefore
generates the exact current backup only if the operator clicks Download Flight Recorder.
Explicit/custom recorder paths preserve the historical eager-bytes API for tests and
diagnostics. Large-file gzip behavior and visible filename/MIME metadata are preserved.

Operational/export memory containment only. No scheduler predicate, watchdog ownership,
provider request, market-data value, discovery, VWAP, SuperTrend, participation,
expansion, scoring, ranking, qualification, alerts/audio, execution, or orders change.
"""
from __future__ import annotations

import gzip
from pathlib import Path


AUTHORITY = "EXPORT_MEMORY_CONTAINMENT_ONLY"
DEFAULT_FLIGHT_RECORDER_PATH = Path("data/flight_recorder.jsonl")
_DEFERRED_MARKER = "_gs448_deferred_flight_recorder"
_GZIP_MARKER = "_gs448_gzip_payload"
_INSTALL_GENERATION = object()


def _inherit_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _is_default_path(path: object) -> bool:
    try:
        return Path(path) == DEFAULT_FLIGHT_RECORDER_PATH
    except (TypeError, ValueError):
        return False


def _expects_gzip(path: Path) -> bool:
    from . import gs364_live_operator_containment as gs364

    try:
        return path.exists() and path.stat().st_size >= int(gs364.LARGE_EXPORT_BYTES)
    except OSError:
        return False


def _normalize_payload_mode(payload: object, *, gzip_expected: bool) -> bytes:
    from . import gs364_live_operator_containment as gs364

    if callable(payload):
        payload = payload()
    raw = bytes(payload or b"")
    is_gzip = gs364._is_gzip_payload(raw)
    if gzip_expected:
        if is_gzip:
            return raw
        return gzip.compress(raw, compresslevel=5, mtime=0)
    if is_gzip:
        return gzip.decompress(raw)
    return raw


def deferred_flight_recorder_export(exporter, recorder):
    """Return bytes for custom recorders or lazy data for Walter's live recorder."""
    path = Path(recorder.path)
    if not _is_default_path(path):
        return exporter(recorder)

    gzip_expected = _expects_gzip(path)

    def materialize() -> bytes:
        return _normalize_payload_mode(
            exporter(recorder),
            gzip_expected=gzip_expected,
        )

    setattr(materialize, _DEFERRED_MARKER, True)
    setattr(materialize, _GZIP_MARKER, gzip_expected)
    materialize._gs448_authority = AUTHORITY
    materialize._gs448_trading_logic_changed = False
    return materialize


def _argument(args: tuple, kwargs: dict, index: int, name: str):
    if name in kwargs:
        return kwargs[name]
    return args[index] if len(args) > index else None


def _replace_argument(
    args: tuple,
    kwargs: dict,
    index: int,
    name: str,
    value: object,
) -> tuple[tuple, dict]:
    mutable_args = list(args)
    updated_kwargs = dict(kwargs)
    if len(mutable_args) > index:
        mutable_args[index] = value
    else:
        updated_kwargs[name] = value
    return tuple(mutable_args), updated_kwargs


def _install_flight_export() -> None:
    from .flight_recorder import FlightRecorder

    current = FlightRecorder.export_bytes
    if getattr(current, "_gs448_install_generation", None) is _INSTALL_GENERATION:
        return

    def export_bytes(self):
        return deferred_flight_recorder_export(current, self)

    _inherit_markers(export_bytes, current)
    export_bytes._gs448_deferred_flight_recorder = True
    export_bytes._gs448_install_generation = _INSTALL_GENERATION
    export_bytes._gs448_original = current
    FlightRecorder.export_bytes = export_bytes


def _install_download_metadata() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs448_install_generation", None) is _INSTALL_GENERATION:
        return

    def download_button(*args, **kwargs):
        data = _argument(args, kwargs, 1, "data")
        if callable(data) and getattr(data, _DEFERRED_MARKER, False):
            if getattr(data, _GZIP_MARKER, False):
                file_name = _argument(args, kwargs, 2, "file_name")
                mime = _argument(args, kwargs, 3, "mime")
                adjusted_args, adjusted_kwargs = args, kwargs
                name = str(file_name or "")
                adjusted_name = name + ".gz" if name and not name.endswith(".gz") else file_name
                if adjusted_name != file_name:
                    adjusted_args, adjusted_kwargs = _replace_argument(
                        adjusted_args, adjusted_kwargs, 2, "file_name", adjusted_name
                    )
                if mime != "application/gzip":
                    adjusted_args, adjusted_kwargs = _replace_argument(
                        adjusted_args, adjusted_kwargs, 3, "mime", "application/gzip"
                    )
                args, kwargs = adjusted_args, adjusted_kwargs
        return current(*args, **kwargs)

    _inherit_markers(download_button, current)
    download_button._gs448_deferred_flight_recorder = True
    download_button._gs448_install_generation = _INSTALL_GENERATION
    download_button._gs448_original = current
    st.download_button = download_button

    try:
        from . import ui

        ui.st.download_button = download_button
    except Exception:
        pass


def install() -> None:
    """Defer only Walter's default live Flight Recorder download payload."""
    _install_flight_export()
    _install_download_metadata()
