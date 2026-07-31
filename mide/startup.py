"""Timestamped, non-blocking startup instrumentation for Walter."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from threading import Timer
from time import monotonic
from typing import Callable, Iterator, TypeVar


LOGGER = logging.getLogger("walter.startup")
LOGGER.setLevel(logging.INFO)
STARTED_AT = monotonic()
SLOW_STARTUP_SECONDS = 10.0
_T = TypeVar("_T")


def log_startup(component: str, message: str = "starting") -> None:
    """Emit one consistently timestamped startup event."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    LOGGER.info(
        "[%s] startup +%.3fs component=%s %s",
        timestamp,
        monotonic() - STARTED_AT,
        component,
        message,
    )


@contextmanager
def startup_step(component: str) -> Iterator[None]:
    """Log a step and identify it if it is still running after ten seconds."""
    started = monotonic()
    log_startup(component)
    timer = Timer(
        SLOW_STARTUP_SECONDS,
        log_startup,
        args=(component, f"delay exceeded {SLOW_STARTUP_SECONDS:.0f}s"),
    )
    timer.daemon = True
    timer.start()
    try:
        yield
    except Exception as exc:
        log_startup(
            component,
            f"failed after {monotonic() - started:.3f}s: {type(exc).__name__}: {exc}",
        )
        raise
    else:
        log_startup(component, f"complete in {monotonic() - started:.3f}s")
    finally:
        timer.cancel()


def instrument_startup(component: str) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Decorate a component so its start, duration, and delay are reported."""
    def decorate(function: Callable[..., _T]) -> Callable[..., _T]:
        def instrumented(*args, **kwargs) -> _T:
            with startup_step(component):
                return function(*args, **kwargs)

        return instrumented

    return decorate
