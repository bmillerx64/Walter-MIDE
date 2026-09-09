"""GS392: pin final operator-state ordering and make alert tiers unmistakable.

Live validation on 2026-09-08 showed two presentation regressions after the GS391
strategy-truth deployment:
* DEVELOPING cards could again render below CHASE / WAIT because later UI wrappers
  inherited the old GS369 marker even when the ordering wrapper was no longer the
  outermost call boundary;
* LOOK NOW used a two-note pattern that was still too similar to Walter's routine
  single chime during active scanning.

GS392 is presentation/audio only. It does not change discovery, candidate membership,
market data, VWAP/ST evidence, scoring, ranking, qualification, thresholds, readiness,
execution, or orders.
"""
from __future__ import annotations


# Keep routine scans calm and make chart-review / entry-review urgency obvious.
ROUTINE_PATTERN = ((620, 0.00),)
LOOK_NOW_PATTERN = ((900, 0.00), (1480, 0.28))
WATCH_FOR_ENTRY_PATTERN = ((740, 0.00), (1047, 0.17), (1568, 0.34))


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_final_order(ui, attr: str) -> None:
    """Wrap the current live renderer even if it inherited an older order marker."""
    current = getattr(ui, attr)
    if getattr(current, "_gs392_final_operator_order", False):
        return

    from .gs369_escalation_priority_order import ordered_escalation_records

    def final_ordered_renderer(records: list[dict]) -> None:
        return current(ordered_escalation_records(records))

    _inherit(final_ordered_renderer, current)
    final_ordered_renderer._gs392_final_operator_order = True
    final_ordered_renderer._gs392_original = current
    setattr(ui, attr, final_ordered_renderer)


def _install_distinct_audio_patterns() -> None:
    """Replace only Web Audio cadence/frequency patterns; preserve semantic tiers."""
    from . import gs367_browser_audio_broker as broker

    broker.TONE_PATTERNS.clear()
    broker.TONE_PATTERNS.update(
        {
            1: ROUTINE_PATTERN,
            2: LOOK_NOW_PATTERN,
            3: WATCH_FOR_ENTRY_PATTERN,
        }
    )


def install() -> None:
    """Install as the final late presentation/audio boundary."""
    from . import ui

    _install_final_order(ui, "render_escalation_engine")
    _install_final_order(ui, "render_walter_mission_control")
    _install_distinct_audio_patterns()

    # GS393 deliberately installs after the final GS392 presentation/audio boundary.
    # It changes operator ignition semantics and the lifetime of the separate extreme-
    # mover banner, while leaving scanner qualification/execution authority untouched.
    from .gs393_ignition_truth_extreme_decay import install as install_gs393

    install_gs393()

    # GS394 is narrower still: a chart-review-only re-arm for a previously extended
    # mover that has digested the move and produces a fresh 1m bullish reset while 3m
    # remains confirmed. Existing anti-chase entry/readiness authority is untouched.
    from .gs394_consolidation_rearm import install as install_gs394

    install_gs394()

    # GS395 widens discovery only: a bounded second page for Webull 5-minute movers
    # and absolute-volume rankings. It intentionally leaves RVOL as context and does
    # not alter any downstream qualification or execution threshold.
    from .gs395_earlier_discovery_breadth import install as install_gs395

    install_gs395()

    # GS396 promotes genuine Webull 30-second ST state from recorder-only evidence to
    # the first attention tripwire. It is deliberately installed last so the live
    # Scanner V2 boundary sees every earlier strategy correction, while its entry
    # wrapper strips 30s flip fields before legacy entry-trigger evaluation. Thus:
    # 30s = investigate, 1m = primary ignition, 3m = confirmation.
    from .gs396_live_30s_tripwire import install as install_gs396

    install_gs396()

    # GS397 closes the live-path split exposed by the 2026-09-08 close: GS378's
    # canonical 30s alignment receives the same completed Webull TICK-reconstructed
    # bars that GS396 already proved in the recorder. A fresh flip may enter the
    # operator investigation view, but it does not gain 1m entry authority.
    from .gs397_canonical_30s_tripwire_truth import install as install_gs397

    install_gs397()

    # GS398 makes a genuinely new visible LOOK NOW transition own tier-2 audio ahead
    # of routine/coiling alerts, while preserving any simultaneous tier-3 entry alert.
    # GS366/367 remain the exactly-once delivery authority across Streamlit reruns.
    from .gs398_look_now_audio_transition import install as install_gs398

    install_gs398()
