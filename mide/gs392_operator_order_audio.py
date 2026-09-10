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

    # GS399 leaves all alert truth/routing intact and changes only the browser audio
    # envelope after the winning semantic tier has been selected. Live validation on
    # 2026-09-09 proved the existing short two/three-note blips were not distinctive
    # enough to reliably pull operator attention away from Webull.
    from .gs399_attention_audio_envelope import install as install_gs399

    install_gs399()

    # GS401 is the final presentation anchor for Opportunity State cards. It sorts
    # only after the complete actionable/awareness/reclaim collection has been built,
    # so later visibility enrichment cannot undo WATCH/LOOK/DEVELOPING/CHASE priority.
    from .gs401_final_opportunity_order import install as install_gs401

    install_gs401()

    # GS404 is a chart-review-only retest attention path. A current Webull mover that
    # was extended on the prior scan, resets into the established +/-2% VWAP window,
    # retains bullish 1m SuperTrend, and still carries participation/flow becomes
    # LOOK NOW without gaining scanner qualification, readiness, or entry authority.
    from .gs404_reset_retest_look_now import install as install_gs404

    install_gs404()

    # GS406 is presentation-only operator memory. A newly visible LOOK NOW or WATCH
    # FOR ENTRY remains pinned for five minutes while Walter continues scanning, so a
    # fast subsequent recategorization cannot erase the event while the operator is
    # validating the chart in Webull.
    from .gs406_operator_alert_latch import install as install_gs406

    install_gs406()

    # GS407 isolates the sidebar Diagnostics widgets from app-wide Streamlit reruns.
    # Toggling lookup controls or running the explicit connection test must not enter
    # or delay Walter's live scan orchestration while autoscan owns the market loop.
    from .gs407_sidebar_diagnostics_isolation import install as install_gs407

    install_gs407()

    # GS408 keeps the prior completed trading surface mounted while the next blocking
    # Streamlit scan rerun is in flight. Only app.py's seven mission-control empty
    # placeholders are deferred; the new scan replaces them when rendering begins.
    from .gs408_preserve_completed_scan_during_rerun import install as install_gs408

    install_gs408()

    # GS411 is observational timing only. It runs after GS408 at GS410's safe
    # post-package startup boundary and records scheduler/rerun/watchdog/persistence
    # geometry into each Flight Recorder scan without changing cadence or trading.
    from .gs411_scan_cadence_timing_truth import install as install_gs411

    install_gs411()

    # GS413 runs after GS411 so there is one process-wide AutoScan cadence owner.
    # Passive Streamlit sessions still adopt/render completed evidence and alerts,
    # but cannot manufacture competing automatic requests or completion-time drift.
    from .gs413_single_process_autoscan_authority import install as install_gs413

    install_gs413()

    # Preserve the established reboot contract: if the process watchdog is already
    # active, the request flag may represent the in-flight scan itself. Idle passive
    # sessions are still denied by GS413's later scheduler/view authority.
    from .gs413_inflight_intent_preservation import install as install_gs413_inflight

    install_gs413_inflight()

    # GS414 is the final Opportunity State presentation anchor. It freezes the fully
    # enriched actionable collection in canonical operator-priority order for the
    # duration of the renderer so nested/later wrappers cannot append DEVELOPING
    # records below CHASE / WAIT after the final sort.
    from .gs414_final_enriched_opportunity_order import install as install_gs414

    install_gs414()
