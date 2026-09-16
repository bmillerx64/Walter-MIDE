"""GS427/GS472: hard-bind live runtime truth to Walter's proven recorder path.

GS427 made latency/build identity survive stale/hot-reloaded recorder bindings by
walking the actual active ``FlightRecorder.record_scan`` wrapper graph and patching
the ``persist_replayable_scan`` global that graph really calls.

Fresh Sep. 16 Flight Recorder #74 proves that same call path is the only reliable
hot-deploy foothold for the retained live provider as well. Build ``180e25a29b04``
(GS471) was CURRENT for 15 scans from 17:48:57Z through 18:04:01Z, yet every scan
still lacked ``stream_30s_health`` and all 24 GS390 validation observations still had
``thirty_second.latest_closed = None``. In contrast, GS427's runtime identity remained
present on every scan and reported its provider source as the GS425 Stage-6 trace.

GS472 therefore uses that already-proven active recorder boundary to touch the exact
provider that just produced the completed scan. Resolving the provider now performs
one bounded infrastructure-only repair through GS470's production guard: re-enable
streaming when a genuine retained Webull SDK provider was left REST-only, rebind the
active GS379 provider registry, and repair missing retained TICK aggregation hooks.
It does *not* open a network subscription from the recorder path; the next ordinary
``initialize_quotes`` cycle remains the owner of stream connection/subscription.

The same active-provider health snapshot is written both at top level and inside
``recorder_runtime_identity``. The nested copy is deliberate: a retained pre-GS472
GS427 wrapper still performs global lookups for ``_active_provider`` and
``_runtime_identity``, so a hot reload can gain the GS472 self-heal/telemetry even if
that older wrapper function object survives.

No discovery, provider request, market-data value, indicator, gate, score, threshold,
qualification, ranking, alert/audio, execution, session authority, or order behavior
is changed. Genuine Webull OpenAPI TICK remains the only 30-second source.
"""
from __future__ import annotations

from functools import wraps
from types import FunctionType
from typing import Any
import weakref


AUTHORITY = "OBSERVATIONAL_ONLY"
_BINDING_NAME = "FlightRecorder.record_scan.__globals__.persist_replayable_scan"
_INSTALL_GENERATION = object()
_LAST_ACTIVE_PROVIDER_REF = None


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
    # A clean process should always find the base function. Falling back to the
    # module dictionary keeps the installer safe if a future wrapper hides its
    # closure while still preserving the same public module contract.
    return flight_recorder.__dict__


def _remember_active_provider(provider) -> None:
    global _LAST_ACTIVE_PROVIDER_REF
    try:
        _LAST_ACTIVE_PROVIDER_REF = weakref.ref(provider) if provider is not None else None
    except TypeError:
        _LAST_ACTIVE_PROVIDER_REF = None


def _remembered_active_provider():
    reference = _LAST_ACTIVE_PROVIDER_REF
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def _heal_active_provider(provider) -> dict[str, Any]:
    """Repair only genuine retained Webull 30s infrastructure; never start I/O here."""
    if provider is None:
        return {}
    try:
        from . import gs470_30s_activation_truth as gs470

        result = gs470._safe_activate(provider)
    except Exception as exc:
        result = {
            "authority": "LIVE_WEBULL_PRODUCTION_30S_ACTIVATION",
            "runtime_hard_bind": True,
            "activation_error": type(exc).__name__,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
            "entry_authority_changed": False,
        }
    diagnostics = getattr(provider, "diagnostics", None)
    if isinstance(diagnostics, dict):
        stream = diagnostics.setdefault("webull_stream", {})
        if isinstance(stream, dict):
            stream["gs472_recorder_provider_self_heal"] = {
                "performed": True,
                "network_subscription_started_here": False,
                "next_initialize_owns_stream_start": True,
                "genuine_webull_tick_only": True,
                "trading_authority_changed": False,
            }
    return result


def _provider_health(provider) -> dict[str, Any]:
    try:
        from . import gs470_30s_activation_truth as gs470

        health = dict(gs470.stream_30s_health(provider))
    except Exception as exc:
        health = {
            "authority": "LIVE_WEBULL_PRODUCTION_30S_ACTIVATION",
            "provider_present": provider is not None,
            "health_error": type(exc).__name__,
            "runtime_hard_bind": True,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }
    health["gs472_recorder_provider_self_heal"] = True
    health["network_subscription_started_here"] = False
    return health


def _active_provider():
    """Resolve and self-heal the exact provider observed on the completed live scan."""
    from . import gs425_latency_truth_recorder as gs425

    provider = gs425._provider_from_trace()
    source = "gs425_stage6_trace"
    if provider is None:
        try:
            from .gs386_30s_observational_recorder import _active_provider as stream_provider

            provider = stream_provider()
        except Exception:
            provider = None
        source = "gs379_active_provider" if provider is not None else "unavailable"

    if provider is not None:
        _remember_active_provider(provider)
        _heal_active_provider(provider)
    return provider, source


def _runtime_identity(provider_source: str) -> dict[str, Any]:
    from .version import BUILD

    freshness = BUILD.freshness()
    provider = _remembered_active_provider()
    return {
        "authority": AUTHORITY,
        "gs427_hard_bind": True,
        "gs472_provider_self_heal": True,
        "binding": _BINDING_NAME,
        "provider_source": provider_source,
        "version": BUILD.version,
        "loaded_git_sha": BUILD.loaded_git_sha,
        "checkout_git_sha": freshness.get("checkout_git_sha"),
        "runtime_stale": bool(freshness.get("runtime_stale")),
        "runtime_status": freshness.get("status"),
        "stream_30s_health": _provider_health(provider),
        "trading_logic_changed": False,
    }


def install() -> None:
    """Bind latency/build/30s health to the persistence global the active recorder uses."""
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
        augmented["stream_30s_health"] = _provider_health(provider)
        # Add the field here even if GS425's ordinary module-level wrapper is absent
        # or attached to a stale module generation. If GS425 is already inside this
        # chain it may rebuild the same key, which is harmless and remains
        # observational only.
        augmented["latency_truth"] = build_latency_truth(provider)
        return current(recorder, augmented, records, *args, **kwargs)

    persist_with_hard_bound_latency._gs427_flight_recorder_latency_hard_bind = True
    persist_with_hard_bound_latency._gs472_live_provider_self_heal = True
    persist_with_hard_bound_latency._gs427_install_generation = _INSTALL_GENERATION
    persist_with_hard_bound_latency._gs427_original = current
    globals_dict["persist_replayable_scan"] = persist_with_hard_bound_latency

    # Keep the public module attribute synchronized when an older retained base
    # function supplied a distinct globals dictionary. Do not replace a newer
    # module chain unless both dictionaries are in fact the same active binding.
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_hard_bound_latency
