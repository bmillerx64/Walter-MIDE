"""GS427: make live latency truth survive stale/hot-reloaded recorder bindings.

Sep. 10 live Flight Recorder exports continued to contain GS411 cadence timing but
not GS425 ``latency_truth``.  The missing field means the observational wrapper was
not on the exact ``persist_replayable_scan`` global reached by the active
``FlightRecorder.record_scan`` call path.  Walter has accumulated several historical
record_scan wrappers, and Streamlit can retain those function objects across a hot
checkout transition.

GS427 is diagnostics only.  It walks the *actual* active ``record_scan`` wrapper
chain, finds the underlying function whose globals belong to ``mide.flight_recorder``,
and installs the latency wrapper in that exact globals dictionary.  It also writes a
small runtime-build identity beside each scan so future downloaded Flight Recorders
prove which Python runtime and checkout produced them.

No discovery, provider request, market-data value, indicator, gate, score, threshold,
qualification, alert/audio, execution, or order behavior changes.
"""
from __future__ import annotations

from functools import wraps
from types import FunctionType
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
_BINDING_NAME = "FlightRecorder.record_scan.__globals__.persist_replayable_scan"
_INSTALL_GENERATION = object()


def _walk_functions(root) -> list[FunctionType]:
    """Return callable functions reachable through Walter's wrapper chain."""
    stack = [root]
    seen: set[int] = set()
    found: list[FunctionType] = []
    while stack:
        current = stack.pop()
        if not isinstance(current, FunctionType) or id(current) in seen:
            continue
        seen.add(id(current))
        found.append(current)

        wrapped = getattr(current, "__wrapped__", None)
        if isinstance(wrapped, FunctionType):
            stack.append(wrapped)
        for name, value in getattr(current, "__dict__", {}).items():
            if name.endswith("_original") and isinstance(value, FunctionType):
                stack.append(value)
        for cell in getattr(current, "__closure__", ()) or ():
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if isinstance(value, FunctionType):
                stack.append(value)
    return found


def _active_recorder_globals() -> dict[str, Any]:
    """Locate the globals dictionary used by the base active recorder method."""
    from . import flight_recorder

    for function in _walk_functions(flight_recorder.FlightRecorder.record_scan):
        globals_dict = getattr(function, "__globals__", {})
        if globals_dict.get("__name__") != "mide.flight_recorder":
            continue
        if callable(globals_dict.get("persist_replayable_scan")):
            return globals_dict
    # A clean process should always find the base function.  Falling back to the
    # module dictionary keeps the installer safe if a future wrapper hides its
    # closure while still preserving the same public module contract.
    return flight_recorder.__dict__


def _active_provider():
    """Resolve the provider from GS425 trace first, then the proven GS379 registry."""
    from . import gs425_latency_truth_recorder as gs425

    provider = gs425._provider_from_trace()
    if provider is not None:
        return provider, "gs425_stage6_trace"
    try:
        from .gs386_30s_observational_recorder import _active_provider as stream_provider

        provider = stream_provider()
    except Exception:
        provider = None
    return provider, "gs379_active_provider" if provider is not None else "unavailable"


def _runtime_identity(provider_source: str) -> dict[str, Any]:
    from .version import BUILD

    freshness = BUILD.freshness()
    return {
        "authority": AUTHORITY,
        "gs427_hard_bind": True,
        "binding": _BINDING_NAME,
        "provider_source": provider_source,
        "version": BUILD.version,
        "loaded_git_sha": BUILD.loaded_git_sha,
        "checkout_git_sha": freshness.get("checkout_git_sha"),
        "runtime_stale": bool(freshness.get("runtime_stale")),
        "runtime_status": freshness.get("status"),
        "trading_logic_changed": False,
    }


def install() -> None:
    """Bind GS425 evidence to the persistence global the active recorder really uses."""
    from . import flight_recorder
    from .gs425_latency_truth_recorder import build_latency_truth

    globals_dict = _active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, "_gs427_install_generation", None) is _INSTALL_GENERATION:
        return

    @wraps(current)
    def persist_with_hard_bound_latency(recorder, scan: dict, records, *args, **kwargs):
        provider, provider_source = _active_provider()
        augmented = dict(scan)
        augmented["recorder_runtime_identity"] = _runtime_identity(provider_source)
        # Add the field here even if GS425's ordinary module-level wrapper is absent
        # or attached to a stale module generation.  If GS425 is already inside this
        # chain it may rebuild the same key, which is harmless and remains
        # observational only.
        augmented["latency_truth"] = build_latency_truth(provider)
        return current(recorder, augmented, records, *args, **kwargs)

    persist_with_hard_bound_latency._gs427_flight_recorder_latency_hard_bind = True
    persist_with_hard_bound_latency._gs427_install_generation = _INSTALL_GENERATION
    persist_with_hard_bound_latency._gs427_original = current
    globals_dict["persist_replayable_scan"] = persist_with_hard_bound_latency

    # Keep the public module attribute synchronized when an older retained base
    # function supplied a distinct globals dictionary.  Do not replace a newer
    # module chain unless both dictionaries are in fact the same active binding.
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_hard_bound_latency
