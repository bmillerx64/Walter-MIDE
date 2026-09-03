from mide import ui
from mide.gs373_operator_visibility_freshness import (
    MAX_OPERATOR_BAR_AGE_SECONDS,
    install,
    operator_visibility_reason,
    operator_visible,
)


def _record(**overrides):
    record = {
        "symbol": "TEST",
        "qualified_for_watch": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.5,
        "bar_age_seconds": 30.0,
    }
    record.update(overrides)
    return record


def test_fami_style_far_below_vwap_is_hidden_from_operator_workflow_only():
    install()
    fami = _record(
        symbol="FAMI",
        vwap_relation="below",
        vwap_distance_pct=-7.0,
        supertrend_bullish=True,
    )

    assert ui.is_actionable_candidate(fami) is True
    assert operator_visible(fami) is False
    assert "below VWAP" in operator_visibility_reason(fami)
    assert ui.actionable_candidate_records([fami]) == []
    # This is not a scanner rejection; diagnostics/history retain the raw record.
    assert ui.rejected_candidate_records([fami]) == []


def test_near_below_vwap_reclaim_watch_remains_visible():
    install()
    reclaim = _record(
        symbol="RECL",
        vwap_relation="testing",
        vwap_distance_pct=-0.8,
    )

    assert operator_visible(reclaim) is True
    assert ui.actionable_candidate_records([reclaim]) == [reclaim]


def test_above_vwap_extended_name_remains_visible_for_chase_wait_guidance():
    install()
    extended = _record(symbol="RUNR", vwap_distance_pct=6.0)

    assert operator_visible(extended) is True
    assert ui.actionable_candidate_records([extended]) == [extended]


def test_stale_source_bar_is_hidden_until_fresh_evidence_returns():
    install()
    stale = _record(
        symbol="LAG",
        bar_age_seconds=MAX_OPERATOR_BAR_AGE_SECONDS + 1,
    )
    fresh = _record(
        symbol="LIVE",
        bar_age_seconds=MAX_OPERATOR_BAR_AGE_SECONDS,
    )

    assert operator_visible(stale) is False
    assert "source bar" in operator_visibility_reason(stale)
    assert ui.actionable_candidate_records([stale, fresh]) == [fresh]


def test_missing_bar_age_does_not_break_legacy_records():
    install()
    legacy = _record(symbol="OLD")
    legacy.pop("bar_age_seconds")

    assert operator_visible(legacy) is True
    assert ui.actionable_candidate_records([legacy]) == [legacy]


def test_gs373_wrapper_is_installed_once_and_keeps_prior_wrapper_markers():
    install()
    first = ui.actionable_candidate_records
    install()

    assert ui.actionable_candidate_records is first
    assert getattr(first, "_gs373_operator_visibility_freshness", False) is True
