"""GS446: remove Candidate History payload work from scheduled scan reruns.

Live validation of merged GS445 on 2026-09-11 showed that incremental gzip generation
removed whole-file recompression but did not remove the growing pre-scan handoff delay.
The scheduler still observed its cadence deadline promptly, while the time from first
due observation to the next scan attempt grew with session age.

The remaining boundary is Streamlit download materialization. ``app.py`` calls
``get_store().export_bytes()`` while rendering the sidebar, before scan dispatch.
Even with GS445's O(delta) compressor, that eager call still returns the complete
growing payload to Streamlit on every full-app rerun, which Streamlit must register,
hash/serialize, and retain before Walter can reach the scan-attempt boundary.

Streamlit 1.62 supports a callable ``data`` argument for ``st.download_button``. GS446
therefore changes only the *default live Candidate History store's* export surface: the
eager app call now returns a zero-argument callable, and the exact bytes are generated
only when the operator clicks Download Candidate History. Explicit/custom MemoryStore
paths preserve the historical bytes-returning API used by tests and diagnostics.

For large files, GS446 also carries the render-time gzip intent on the deferred callable
so GS364's established ``.gz`` filename and ``application/gzip`` metadata remain exact.
The click-time materializer stabilizes that chosen mode even if the file crosses the
compression threshold between render and click.

Export/presentation latency only. No discovery, provider request, market-data value,
VWAP, SuperTrend, participation, expansion, scoring, ranking, qualification, cadence
predicate, watchdog ownership, alert/audio, execution, or order behavior changes.
"""
from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any, Callable


AUTHORITY = "EXPORT_PRESENTATION_LATENCY_ONLY"
DEFAULT_CANDIDATE_HISTORY_PATH = Path("data/candidate_history.jsonl")
_DEFERRED_MARKER = "_gs446_deferred_candidate_history"
_GZIP_MARKER = "_gs446_gzip_payload"
_INSTALL_GENERATION = object()


def _inherit_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _is_live_default_history(path: object) -> bool:
    try:
        return Path(path) == DEFAULT_CANDIDATE_HISTORY_PATH
    except (TypeError, ValueError):
        return False


def _expects_gzip(path: Path) -> bool:
    from . import gs364_live_operator_containment as gs364

    try:
        return path.exists() and path.stat().st_size >= int(gs364.LARGE_EXPORT_BYTES)
    except OSError:
        return False


def _normalize_payload_mode(payload: object, *, gzip_expected: bool) -> bytes:
    """Keep the render-time filename/MIME mode stable until the later click."""
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


def deferred_candidate_history_export(exporter: Callable[[Any], object], store) -> object:
    """Return bytes for custom stores or a lazy callable for the live default store."""
    path = Path(store.path)
    if not _is_live_default_history(path):
        return exporter(store)

    gzip_expected = _expects_gzip(path)

    def materialize() -> bytes:
        return _normalize_payload_mode(
            exporter(store),
            gzip_expected=gzip_expected,
        )

    setattr(materialize, _DEFERRED_MARKER, True)
    setattr(materialize, _GZIP_MARKER, gzip_expected)
    materialize._gs446_authority = AUTHORITY
    materialize._gs446_trading_logic_changed = False
    return materialize


def deferred_download_metadata(
    data: object,
    file_name: object,
    mime: object,
) -> tuple[object, object]:
    """Preserve GS364's visible gzip metadata without forcing payload generation."""
    if not callable(data) or not getattr(data, _DEFERRED_MARKER, False):
        return file_name, mime
    if not getattr(data, _GZIP_MARKER, False):
        return file_name, mime

    name = str(file_name or "")
    if name and not name.endswith(".gz"):
        file_name = name + ".gz"
    return file_name, "application/gzip"


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


def _install_memory_export() -> None:
    from . import memory

    current = memory.MemoryStore.export_bytes
    if getattr(current, "_gs446_install_generation", None) is _INSTALL_GENERATION:
        return

    def export_bytes(self):
        return deferred_candidate_history_export(current, self)

    _inherit_markers(export_bytes, current)
    export_bytes._gs446_deferred_candidate_history = True
    export_bytes._gs446_install_generation = _INSTALL_GENERATION
    export_bytes._gs446_original = current
    memory.MemoryStore.export_bytes = export_bytes


def _install_download_metadata() -> None:
    import streamlit as st

    current = st.download_button
    if getattr(current, "_gs446_install_generation", None) is _INSTALL_GENERATION:
        return

    def download_button(*args, **kwargs):
        data = _argument(args, kwargs, 1, "data")
        file_name = _argument(args, kwargs, 2, "file_name")
        mime = _argument(args, kwargs, 3, "mime")
        adjusted_name, adjusted_mime = deferred_download_metadata(
            data, file_name, mime
        )
        adjusted_args, adjusted_kwargs = args, kwargs
        if adjusted_name != file_name:
            adjusted_args, adjusted_kwargs = _replace_argument(
                adjusted_args, adjusted_kwargs, 2, "file_name", adjusted_name
            )
        if adjusted_mime != mime:
            adjusted_args, adjusted_kwargs = _replace_argument(
                adjusted_args, adjusted_kwargs, 3, "mime", adjusted_mime
            )
        return current(*adjusted_args, **adjusted_kwargs)

    _inherit_markers(download_button, current)
    download_button._gs446_deferred_candidate_history = True
    download_button._gs446_install_generation = _INSTALL_GENERATION
    download_button._gs446_original = current
    st.download_button = download_button

    # ``mide.ui`` references the same Streamlit module object, but assigning
    # explicitly keeps hot-reload/test bindings converged just like GS364.
    try:
        from . import ui

        ui.st.download_button = download_button
    except Exception:
        pass


def install() -> None:
    """Defer only the live Candidate History payload until operator click."""
    _install_memory_export()
    _install_download_metadata()
