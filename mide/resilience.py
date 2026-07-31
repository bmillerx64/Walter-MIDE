"""Shared runtime resilience and structured provider-failure diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
from time import sleep
from typing import Any, Callable


TRANSIENT_EXCEPTIONS = (TimeoutError, ConnectionError)


def record_provider_failure(
    diagnostics: dict[str, Any], *, provider: str, operation: str,
    exception: BaseException, affected_symbols: Iterable[str] = (),
    recovery_action: str,
) -> dict[str, Any]:
    """Append the stable, machine-readable failure shape used by live scans."""
    event = {
        "provider": provider,
        "operation": operation,
        "exception": f"{type(exception).__name__}: {exception}",
        "affected_symbols": sorted({str(s).strip().upper() for s in affected_symbols if s}),
        "recovery_action": recovery_action,
    }
    key = "provider_failures"
    if key in diagnostics and not isinstance(diagnostics[key], list):
        key = "provider_failure_diagnostics"
    diagnostics.setdefault(key, []).append(event)
    return event


def retry_transient(
    operation: Callable[[], Any], *, attempts: int = 2,
    delay_seconds: float = 0.05,
) -> Any:
    """Retry connection and timeout failures without retrying malformed data."""
    last: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            return operation()
        except TRANSIENT_EXCEPTIONS as exc:
            last = exc
            if attempt + 1 < attempts:
                sleep(delay_seconds * (attempt + 1))
    assert last is not None
    raise last
