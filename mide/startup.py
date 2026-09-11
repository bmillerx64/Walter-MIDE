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


def ensure_late_runtime_installers() -> None:
    """Install the GS384+ runtime chain after the parent package import is complete.

    ``mide.startup`` can itself be imported while ``mide.__init__`` is still running,
    so the late chain must not execute at module import time. app.py calls
    ``log_startup('entering app.py')`` immediately after its first MIDE import; at
    that point Python has released the parent package import lock and GS384 can safely
    import GS386+ without the hot-reload lock inversion fixed by GS410.
    """
    from .gs384_diagnostic_signal_to_noise import install as install_late_chain
    from .gs414_final_enriched_opportunity_order import install as install_final_order
    from .gs416_validity_symbol_suffix import install as install_gs416
    from .gs423_convergence_handoff_efficiency import install as install_gs423
    from .gs424_warm_scan_history_cache import install as install_gs424
    from .gs425_latency_truth_recorder import install as install_gs425
    from .gs426_intraday_free_float_cache import install as install_gs426
    from .gs427_flight_recorder_latency_hard_bind import install as install_gs427
    from .gs428_scheduler_deadtime_release import install as install_gs428
    from .gs435_due_deadline_owner_handoff import install as install_gs435
    from .gs445_incremental_backup_exports import install as install_gs445
    from .gs446_deferred_candidate_history_download import install as install_gs446
    from .gs448_deferred_flight_recorder_download import install as install_gs448

    install_late_chain()
    # GS445 patches GS364's already-installed backup materializer before app.py builds
    # the sidebar download buttons. This removes whole-file recompression from the
    # scheduler-request -> scan-attempt path without changing any cadence predicate.
    install_gs445()
    # GS446 runs immediately outside GS445. The live Candidate History export call now
    # returns a Streamlit-supported deferred callable, so no growing backup payload is
    # generated/registered before app.py can reach the scheduled scan boundary.
    install_gs446()
    # GS448 closes the matching Flight Recorder leak. app.py still renders the same
    # button after scan orchestration, but Streamlit now receives only a callable on
    # ordinary reruns and materializes recorder bytes only when the operator clicks it.
    install_gs448()
    install_gs416()
    # GS423 runs after the legacy chain so warm Streamlit deployments cannot retain an
    # inherited GS421 marker while missing the efficient analyzed->recorder handoff.
    install_gs423()
    # GS424 owns only the persistent provider's Stage-6 acquisition boundary and never
    # changes the evidence produced by GS423 or any trading contract.
    install_gs424()
    # GS425 runs outside GS424 so it measures the exact effective history boundary and
    # persists the already-computed architecture timing summary into Flight Recorder.
    install_gs425()
    # GS426 caches only the secondary free-float reference lookup across warm scans;
    # the established conservative float decision remains authoritative.
    install_gs426()
    # GS427 is the final recorder-only binding. It makes GS425 timing/build identity
    # survive a retained pre-deploy FlightRecorder.record_scan function graph.
    install_gs427()
    # GS428 runs only after GS413 is active. It removes the obsolete GS412 ten-second
    # completed-scan handoff delay from the production watchdog singleton while the
    # process-wide scheduler owner and no-overlap watchdog remain authoritative.
    install_gs428()
    # GS435 runs outside GS413 so a live passive session can take cadence ownership
    # exactly when the shared real scan-start deadline is due, not after a 120s lease.
    install_gs435()
    # GS436 reasserts the already-established GS414 presentation contract only after
    # every late-runtime installer has converged. Its non-inherited owner sentinel
    # distinguishes the actual outer renderer from a stale wrapper that merely copied
    # GS414's historical marker during a warm Streamlit deployment.
    install_final_order()


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
    # This exact app.py boundary runs only after ``from mide.startup ...`` has
    # completed, which in turn means ``mide.__init__`` is no longer holding the
    # parent package import lock. Keep ordinary provider/startup logging side-effect
    # free so background workers can never trigger the late import chain.
    if component == "entering app.py":
        ensure_late_runtime_installers()


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


def ensure_operator_awareness() -> None:
    """Bind GS375 so market awareness stays separate from entry eligibility."""
    from .gs375_operator_awareness import install

    install()


def ensure_reclaim_watch() -> None:
    """Bind GS376 so rebuilding leaders outrank ordinary DEVELOPING/CHASE noise."""
    from .gs376_reclaim_watch import install

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

# GS375: install after GS373 so stale/far-below-VWAP suppression remains the outer
# safety boundary while current-attention leaders can stay visible without gaining
# entry or alert authorization.
ensure_operator_awareness()

# GS376: install after GS375.  This keeps the GS373 stale-data guard intact while
# allowing only a strict, fresh reconstruction exception for current major leaders;
# awareness-only copies remain denied entry/alert authority.
ensure_reclaim_watch()

# GS377 is deliberately installed from mide.__init__ after GS340.  webull_live
# imports this startup module while LiveWebullProvider is still being defined, so
# importing GS377 here would create a circular webull_live -> startup -> GS377 ->
# webull_connection -> webull_live dependency during ordinary package imports.

# GS410 follows the same rule for the much larger GS384+ late installer chain. It is
# invoked only by app.py's explicit ``log_startup('entering app.py')`` call above,
# after the parent ``mide`` package import has fully completed. GS416 joins that late
# boundary because it patches the already-defined architecture Validity method only.
# GS423 also runs at this boundary, after the entire GS421/422 chain, so it can own
# the final convergence wrapper even across a warm Streamlit deployment. GS424 then
# installs the persistent-provider warm-history cache after all evidence wrappers,
# GS425 measures that final acquisition boundary without changing it, GS426 removes
# repeated same-day Yahoo free-float refreshes without changing float gates, GS427
# hard-binds latency/build evidence to the active recorder call graph, GS428 releases
# obsolete post-scan scheduler deadtime, GS435 removes stale-owner due latency, GS445
# removes append-only backup recompression, GS446 defers the remaining full Candidate
# History payload until operator click, GS448 defers the matching Flight Recorder
# payload, and GS436 hard-binds the final enriched Opportunity State ordering boundary.
