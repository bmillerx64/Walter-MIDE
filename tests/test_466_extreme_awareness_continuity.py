from pathlib import Path

from mide import gs373_operator_visibility_freshness as freshness
from mide import gs375_operator_awareness as awareness
from mide import gs466_extreme_awareness_continuity as gs466


DAY_GAINERS = "Webull native: day_gainers"


def _record(
    *,
    symbol="DLXY",
    pct=121.6867,
    distance=14.081,
    bar_age=304.0,
):
    return {
        "symbol": symbol,
        "pct_change": pct,
        "discovery_reasons": [DAY_GAINERS],
        "vwap_relation": "above" if distance >= 0 else "below",
        "vwap_distance_pct": distance,
        "source_bar_age": bar_age,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "candidate_status": "Removed",
        "status": "WATCH NOW",
        "supertrend_bullish": True,
        "dollar_volume": 132_796_062.0,
    }


def _pre_gs466_reason(record):
    fn = freshness.operator_visibility_reason
    original = getattr(fn, "_gs466_original", fn)
    return original(record)


def test_dlxy_live_shape_is_hidden_only_by_stale_source_bar_before_gs466():
    record = _record()
    reason = _pre_gs466_reason(record)

    assert reason.startswith("source bar is 304s old")
    assert gs466.extreme_awareness_continuity(record, base_reason=reason) is True


def test_gs466_reopens_operator_visibility_for_current_extreme_leader():
    gs466.install()
    record = _record()

    assert freshness.operator_visibility_reason(record) == ""
    assert freshness.operator_visible(record) is True


def test_stale_ordinary_top_mover_remains_hidden():
    gs466.install()
    record = _record(symbol="ORD", pct=50.0, distance=1.0)

    assert freshness.operator_visibility_reason(record).startswith("source bar is 304s old")
    assert freshness.operator_visible(record) is False


def test_far_below_vwap_extreme_is_not_reintroduced_by_stale_bar_exception():
    gs466.install()
    record = _record(symbol="FLUSH", pct=110.0, distance=-7.0)

    reason = freshness.operator_visibility_reason(record)
    assert "below VWAP" in reason
    assert freshness.operator_visible(record) is False


def test_reintroduced_extreme_is_awareness_only_and_cannot_gain_trade_authority():
    gs466.install()
    record = _record()

    rows = awareness.augment_operator_records([record], actionable=[])

    assert len(rows) == 1
    visible = rows[0]
    assert visible["symbol"] == "DLXY"
    assert visible[awareness.AWARENESS_ONLY_KEY] is True
    assert visible["qualified_for_entry"] is False
    assert visible["qualified_for_alert"] is False
    assert visible["entered_watchlist"] is False


def test_gs466_is_reasserted_after_gs465_at_final_presentation_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")

    assert "gs466_extreme_awareness_continuity" in source
    assert source.index("_install_gs465()") < source.index("_install_gs466()")


def test_gs466_scope_lock_changes_visibility_only():
    source = Path("mide/gs466_extreme_awareness_continuity.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "EXTREME_MOVER_PCT =",
        "MAX_OPERATOR_BAR_AGE_SECONDS =",
        "PARTICIPATION_MIN_",
        "LOOK_NOW_MAX_VWAP",
    )
    for token in forbidden:
        assert token not in source
