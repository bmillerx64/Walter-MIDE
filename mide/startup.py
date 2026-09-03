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


def ensure_operator_card_order() -> None:
    """Bind the final operator-order wrappers before app.py imports UI callables.

    app.py imports this startup module before it performs ``from mide.ui import``.
    Running the GS369/370 installer here closes the import-order gap seen in live
    GS370 validation: the callable that app.py subsequently binds is guaranteed to
    include the current Opportunity State ordering wrapper. Presentation only.
    """
    from .gs369_escalation_priority_order import install

    install()


def ensure_operator_visibility() -> None:
    """Bind GS373's operator-only relevance/freshness filter before app imports."""
    from .gs373_operator_visibility_freshness import install

    install()


def ensure_header_scan_truth() -> None:
    """Bind GS374 so the header timestamp means last completed scan, not deploy."""
    from .gs374_header_scan_truth import install

    install()


# GS371: package-level installers can be correct while app.py still binds an older
# renderer object during a complex Streamlit import/reload sequence. This module is
# app.py's first MIDE import, so enforce the final presentation wrapper immediately
# before app.py binds any renderer names.
ensure_operator_card_order()

# GS373: use the same early binding point so every app-level reference to
# actionable_candidate_records receives the current operator visibility contract.
ensure_operator_visibility()

# GS374: the control-header callable is also imported by name in app.py. Install
# before that binding so the visible timestamp always comes from CompletedScan.
ensure_header_scan_truth()
