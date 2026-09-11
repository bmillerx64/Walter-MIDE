from copy import deepcopy
from pathlib import Path

from mide import gs442_alignment_ladder_truth as gs442
from mide import gs443_market_leader_radar_continuity as gs443
from mide import ui


DAY_GAINERS = "Webull native: day_gainers"


def _leader(
    symbol: str,
    *,
    pct: float,
    dominance: float,
    dollar_volume: float = 2_000_000,
    vwap_relation: str = "below",
    vwap_distance_pct: float = -1.0,
    alignment_score: int = 1,
) -> dict:
    return {
        "symbol": symbol,
        "pct_change": pct,
        "dollar_volume": dollar_volume,
        "market_dominance_score": dominance,
        "discovery_reasons": [DAY_GAINERS],
        "vwap_relation": vwap_relation,
        "vwap_distance_pct": vwap_distance_pct,
        "alignment_score": alignment_score,
        "supertrend_bullish": False,
        "supertrend_flip": False,
        "volume_acceleration": 1.0,
        "acceleration_ratio": 1.0,
        "rvol_proxy": 1.0,
        "volume_above_preceding_15m_pace": False,
        "broke_previous_15m_high_with_volume": False,
        "breakout_confirmed": False,
    }


def test_two_extreme_leaders_keep_second_one_visible_without_duplicate():
    # Sep. 11 live shape: BDRX owns GS333's single extreme-mover sightline while
    # TRUG is simultaneously another extraordinary current leader.
    bdrx = _leader("BDRX", pct=81.8, dominance=90.0)
    trug = _leader("TRUG", pct=78.7, dominance=84.7)

    record, event = gs443.market_leader_candidate([bdrx, trug], mission={})

    assert record is trug
    assert event["symbol"] == "TRUG"
    assert event["state"] == "STRUCTURE NOT READY"
    assert event["pct_change"] == 78.7
    assert event["dominance"] == 84.7


def test_single_displayed_extreme_is_not_duplicated_in_continuity_lane():
    bdrx = _leader("BDRX", pct=81.8, dominance=90.0)

    record, event = gs443.market_leader_candidate([bdrx], mission={})

    assert record is None
    assert event is None


def test_mission_focus_and_existing_gs305_attention_still_own_their_symbols():
    focused = _leader("FOCUS", pct=40.0, dominance=88.0)
    mission = {"primary": {"record": focused}, "secondary": None}
    assert gs443.market_leader_candidate([focused], mission=mission) == (None, None)

    # Above VWAP + active participation makes this an established GS305 major-mover
    # attention case, so GS443 must not create a duplicate continuity strip.
    existing_attention = _leader(
        "EARLY", pct=40.0, dominance=88.0, vwap_relation="above", alignment_score=2
    )
    existing_attention["volume_acceleration"] = 1.5
    assert gs443.market_leader_candidate([existing_attention], mission={}) == (None, None)


def test_established_thresholds_and_current_provenance_are_required():
    good = _leader("GOOD", pct=35.0, dominance=82.0)
    record, event = gs443.market_leader_candidate([good], mission={})
    assert record is good
    assert event["symbol"] == "GOOD"

    low_move = _leader("MOVE", pct=19.9, dominance=90.0)
    low_dvol = _leader("DVOL", pct=40.0, dominance=90.0, dollar_volume=249_999)
    low_dom = _leader("DOM", pct=40.0, dominance=77.9)
    stale = _leader("STALE", pct=40.0, dominance=90.0)
    stale["discovery_reasons"] = ["Webull native: absolute_volume"]

    for record in (low_move, low_dvol, low_dom, stale):
        assert gs443.market_leader_candidate([record], mission={}) == (None, None)


def test_selection_is_read_only_and_markup_is_unambiguously_watch_only():
    source = _leader("SAFE", pct=33.0, dominance=83.0)
    before = deepcopy(source)

    _record, event = gs443.market_leader_candidate([source], mission={})
    markup = gs443.market_leader_markup(event)

    assert source == before
    assert "MARKET LEADER RADAR" in markup
    assert "WATCH ONLY" in markup
    assert "NO ENTRY AUTHORITY" in markup
    assert "ENTRY READY" not in markup


def test_gs443_is_activated_from_gs442_in_cold_and_warm_paths():
    source = Path("mide/gs442_alignment_ladder_truth.py").read_text(encoding="utf-8")

    assert "from .gs443_market_leader_radar_continuity import install as install_gs443" in source
    assert source.count("_install_gs443()") >= 2

    gs442.install()
    assert getattr(
        ui.render_walter_mission_control,
        "_gs443_market_leader_radar_continuity",
        False,
    )


def test_gs443_scope_lock_does_not_change_trading_authority():
    source = Path("mide/gs443_market_leader_radar_continuity.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "candidate_status =",
        "attention_score =",
        "market_dominance_score =",
        "play_alert(",
        "request_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)
