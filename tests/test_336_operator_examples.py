from datetime import datetime
from zoneinfo import ZoneInfo

from mide.gs336_early_session_reset_watch import operator_override

NY = ZoneInfo("America/New_York")


def test_clgn_like_early_extension_is_watch_only():
    row = {
        "symbol": "CLGN",
        "pct_change": 90.0,
        "vwap_distance_pct": 12.0,
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "participation_score": 35,
        "expansion_score": 45,
        "evaluated_at": datetime(2026, 8, 31, 10, 5, tzinfo=NY),
    }
    result = operator_override(row)
    assert result and result["label"] == "EARLY SESSION · RESET REQUIRED"


def test_wbuy_like_post_open_rebuild_is_second_entry_forming():
    row = {
        "symbol": "WBUY",
        "pct_change": 30.0,
        "vwap_distance_pct": 3.5,
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "participation_score": 68,
        "expansion_score": 63,
        "evaluated_at": datetime(2026, 8, 31, 10, 35, tzinfo=NY),
    }
    result = operator_override(row)
    assert result and result["label"] == "SECOND ENTRY FORMING"
