"""GS481: warm-deploy-safe Replay / Validation facade for live recorder evidence.

Replay / Validation owns GS481's observational news-story and Webull stream-failure
truth. This historical module remains the runtime seam used by GS484/GS488 and retained
Flight Recorder regressions.

Private helpers intentionally remain mutable delegates: later transport/backoff layers
wrap or rebind _news_truth and _stream_failure_truth. Replay / Validation resolves
those names through this facade at persistence time, preserving the established warm
runtime contract. Missing newer Replay installers safely no-op.

No provider request, subscription start, market-data mutation, trading authority,
execution, or order behavior changes.
"""
from __future__ import annotations


AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = "_walter_gs481_live_evidence_hard_bind_owner"
MAX_FAILURES = 3
MAX_TEXT = 300


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _sanitize(value):
    current = getattr(
        _replay(),
        "sanitize_live_failure",
        None,
    )
    if not callable(current):
        return str(value or "")[:MAX_TEXT]
    return current(value)


def _json_safe(value):
    current = getattr(
        _replay(),
        "live_json_safe",
        None,
    )
    if not callable(current):
        return value
    return current(value)


def _news_truth() -> dict:
    current = getattr(
        _replay(),
        "live_news_truth",
        None,
    )
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "extra_provider_calls": 0,
            "trading_authority_changed": False,
        }
    return current()


def _stream_failure_truth(provider) -> dict:
    current = getattr(
        _replay(),
        "stream_failure_truth",
        None,
    )
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "connection_status": "unknown",
            "network_repair_attempted_here": False,
            "trading_authority_changed": False,
        }
    return current(provider)


def _attach_stream_failure(
    scan: dict,
    provider,
) -> None:
    current = getattr(
        _replay(),
        "attach_stream_failure",
        None,
    )
    if callable(current):
        current(scan, provider)


def install() -> None:
    current = getattr(
        _replay(),
        "install_live_evidence_hard_bind",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "MAX_FAILURES",
    "MAX_TEXT",
    "install",
]
