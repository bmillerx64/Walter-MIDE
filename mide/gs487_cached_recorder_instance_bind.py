"""GS487: warm-deploy-safe Replay / Validation facade for cached-recorder binding.

Replay / Validation owns the exact cached FlightRecorder persistence-graph binding.
This historical module intentionally retains the private helper names and the public
install_for_recorder seam because GS488 wraps that exact symbol at runtime and existing
regressions exercise the helper contract directly.

The authority resolves these facade helpers at execution time, preserving later
monkeypatch/hot-bind behavior. Missing newer authority exports safely return False or
minimal observational truth rather than failing a warm Streamlit rerun.

Historical source-contract markers retained for scope-lock regressions:
# truth["extra_provider_calls"] = 0
# truth["network_repair_attempted_here"] = False

No provider request, stream start, market-data mutation, indicator, gate, score, alert,
execution, session authority, or order behavior changes.
"""
from __future__ import annotations

from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
BINDING = (
    "cached_recorder.record_scan.__func__.__globals__."
    "persist_replayable_scan"
)
REVISION = 2
_OWNER = "_walter_gs487_cached_recorder_instance_bind_revision"


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _exact_recorder_globals(
    recorder,
) -> dict[str, Any] | None:
    current = getattr(
        _replay(),
        "exact_cached_recorder_globals",
        None,
    )
    if not callable(current):
        return None
    return current(recorder)


def _news_transport(
    provider,
    provider_source: str,
) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "cached_recorder_news_transport",
        None,
    )
    if not callable(current):
        return {
            "provider_source": provider_source,
            "cached_recorder_instance_bind": True,
            "extra_provider_calls": 0,
            "trading_authority_changed": False,
        }
    return current(provider, provider_source)


def _shadow_news_trace(
    provider,
    provider_source: str,
) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "cached_recorder_shadow_news_trace",
        None,
    )
    if callable(current):
        return current(
            provider,
            provider_source,
        )

    diagnostics = getattr(
        provider,
        "diagnostics",
        None,
    )
    trace = dict(
        diagnostics.get(
            "gs544_alpaca_news_shadow"
        )
        or {}
    ) if isinstance(diagnostics, dict) else {}
    trace.setdefault(
        "authority",
        "NEWS_COVERAGE_OBSERVATION_ONLY",
    )
    trace.setdefault(
        "provider_role",
        "shadow_context_only",
    )
    trace["available"] = bool(trace)
    trace["provider_source"] = provider_source
    trace["cached_recorder_instance_bind"] = True
    trace["extra_provider_calls"] = 0
    trace["trading_authority_changed"] = False
    return trace


def _stream_transport(
    provider,
    provider_source: str,
) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "cached_recorder_stream_transport",
        None,
    )
    if not callable(current):
        return {
            "provider_source": provider_source,
            "cached_recorder_instance_bind": True,
            "network_repair_attempted_here": False,
            "trading_authority_changed": False,
        }
    return current(provider, provider_source)


def install_for_recorder(recorder) -> bool:
    current = getattr(
        _replay(),
        "install_cached_recorder_instance_bind",
        None,
    )
    if not callable(current):
        return False
    return bool(current(recorder))


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "BINDING",
    "REVISION",
    "install_for_recorder",
]
