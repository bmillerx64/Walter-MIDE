from __future__ import annotations

from pathlib import Path

from mide import gs493_3m_st_retest_truth as gs493
from mide.gs462_preflip_ignition_watch import NEAR_ST_LINE_PCT


def _record(price=0.6244, st=0.5153, bullish=True):
    return {
        "symbol": "TRUG",
        "price": price,
        "timeframes": {
            "3m": {
                "data_available": True,
                "current_supertrend_bullish": bullish,
                "current_above_vwap": True,
                "current_close": price,
                "current_vwap": 0.5990,
                "st_vwap_line_cross": {
                    "latest_supertrend_value": st,
                    "latest_vwap_value": 0.5990,
                },
            }
        },
    }


def test_trug_entry_regression_says_not_at_3m_st_yet():
    truth = gs493.three_minute_st_retest_truth(_record())
    assert truth["state"] == "NOT_AT_3M_ST_YET"
    assert truth["signed_gap_pct"] == 17.473
    assert truth["near_st_line_limit_pct"] == NEAR_ST_LINE_PCT

    view = gs493.state_with_3m_st_truth(
        lambda _record: {"state": "DEVELOPING", "reason": "", "next_step": ""},
        _record(),
    )
    assert "NOT AT 3M ST YET" in view["next_step"]
    assert "0.6244" in view["next_step"]
    assert "0.5153" in view["next_step"]
    assert "VWAP touch does NOT count" in view["next_step"]


def test_within_existing_two_percent_band_is_proximity_not_proof_of_retest():
    record = _record(price=0.5200, st=0.5153, bullish=True)
    truth = gs493.three_minute_st_retest_truth(record)
    assert truth["state"] == "ST_RETEST_CONFIRMED"
    assert 0.0 <= truth["signed_gap_pct"] <= NEAR_ST_LINE_PCT

    view = gs493.state_with_3m_st_truth(
        lambda _record: {"state": "DEVELOPING", "reason": "", "next_step": "Watch structure."},
        record,
    )
    assert view["next_step"].startswith("NEAR 3M ST · PROXIMITY ONLY:")
    assert "does NOT prove a held retest" in view["next_step"]
    assert "Watch structure." in view["next_step"]


def test_price_below_3m_st_is_reclaim_watch_not_confirmed_retest():
    record = _record(price=0.5000, st=0.5153, bullish=True)
    truth = gs493.three_minute_st_retest_truth(record)
    assert truth["state"] == "3M_ST_LOST"
    assert truth["signed_gap_pct"] < 0

    view = gs493.state_with_3m_st_truth(
        lambda _record: {"state": "DEVELOPING", "reason": "", "next_step": ""},
        record,
    )
    assert "3M ST LOST / RECLAIM WATCH" in view["next_step"]


def test_bearish_3m_state_is_lost_even_if_price_near_line():
    truth = gs493.three_minute_st_retest_truth(
        _record(price=0.5200, st=0.5153, bullish=False)
    )
    assert truth["state"] == "3M_ST_LOST"


def test_decision_time_evidence_is_supported_for_replay_truth():
    record = {
        "symbol": "TRUG",
        "decision_time_evidence": {
            "price": 0.6244,
            "timeframes": _record()["timeframes"],
        },
    }
    truth = gs493.three_minute_st_retest_truth(record)
    assert truth["state"] == "NOT_AT_3M_ST_YET"
    assert truth["three_minute_supertrend"] == 0.5153


def test_gs493_does_not_change_base_opportunity_state():
    base = {"state": "LOOK NOW", "reason": "Independent attention.", "next_step": ""}
    view = gs493.state_with_3m_st_truth(lambda _record: dict(base), _record())
    assert view["state"] == "LOOK NOW"
    assert view["reason"] == "Independent attention."
    assert view["three_minute_st_retest_truth"]["entry_authority_changed"] is False
    assert view["three_minute_st_retest_truth"]["readiness_authority_changed"] is False


def test_gs493_installs_after_gs492_at_final_late_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def install() -> None:", 1)[1]
    assert "_install_gs493()" in body
    assert body.index("_install_gs492()") < body.index("_install_gs493()")


def test_scope_lock_is_presentation_only():
    source = (
        Path("mide/authorities/market_evidence.py").read_text(encoding="utf-8")
        + Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "PRESENTATION_GUARDRAIL_ONLY" in source
    assert "VWAP touch does NOT count" in source
