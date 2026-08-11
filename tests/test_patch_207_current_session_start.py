from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from mide.webull_sdk import WebullSDKClient, _clamp_future_session_start


def test_after_midnight_future_session_anchor_moves_to_prior_weekday():
    eastern = ZoneInfo("America/New_York")
    now = datetime(2026, 8, 11, 0, 30, tzinfo=eastern).astimezone(timezone.utc)
    future_anchor = datetime(2026, 8, 11, 4, 0, tzinfo=eastern)

    corrected = _clamp_future_session_start(future_anchor, now=now)

    corrected_eastern = corrected.astimezone(eastern)
    assert corrected_eastern == datetime(2026, 8, 10, 4, 0, tzinfo=eastern)


def test_monday_pre_four_am_skips_weekend_to_friday():
    eastern = ZoneInfo("America/New_York")
    now = datetime(2026, 8, 10, 2, 0, tzinfo=eastern).astimezone(timezone.utc)
    future_anchor = datetime(2026, 8, 10, 4, 0, tzinfo=eastern)

    corrected = _clamp_future_session_start(future_anchor, now=now)

    assert corrected.astimezone(eastern) == datetime(2026, 8, 7, 4, 0, tzinfo=eastern)


def test_history_arguments_leave_end_dated_profile_request_unchanged():
    eastern = ZoneInfo("America/New_York")
    start = datetime(2026, 8, 1, 4, 0, tzinfo=eastern)
    end = datetime(2026, 8, 10, 4, 0, tzinfo=eastern)

    normalized = WebullSDKClient._history_arguments({
        "interval": "m1",
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "count": 1200,
        "include_overnight": True,
    })

    assert normalized["start_time"] == int(start.timestamp() * 1000)
    assert normalized["end_time"] == int(end.timestamp() * 1000)
    assert normalized["trading_sessions"] == "PRE,RTH,ATH"
    assert "OVN" not in normalized["trading_sessions"]
