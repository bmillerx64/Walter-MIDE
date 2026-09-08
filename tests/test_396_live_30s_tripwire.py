from datetime import datetime, timedelta, timezone

from mide import gs396_live_30s_tripwire as gs396
from mide import scanner_v2


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _annotated_sequence(start: datetime) -> list[dict]:
    states = ["bearish", "bearish", "bearish", "bullish", "bullish", "bullish"]
    rows = []
    for index, state in enumerate(states):
        rows.append(
            {
                "timestamp_ms": _ms(start + timedelta(seconds=30 * index)),
                "open": 1.00 + index * 0.01,
                "high": 1.02 + index * 0.01,
                "low": 0.99 + index * 0.01,
                "close": 1.01 + index * 0.01,
                "volume": 1000.0 * (index + 1),
                "supertrend_10_3": 1.03 if state == "bearish" else 1.00,
                "supertrend_state": state,
                "supertrend_ready": True,
            }
        )
    return rows


def test_genuine_30s_bullish_flip_becomes_fresh_attention_tripwire():
    start = datetime(2026, 9, 8, 18, 58, 0, tzinfo=timezone.utc)
    rows = _annotated_sequence(start)
    # Bullish flip bar starts 18:59:30? states index 3 => 18:59:30 close 19:00:00.
    scan_time = start + timedelta(minutes=3, seconds=15)

    result = gs396.tripwire_from_annotated(rows, scan_time)

    assert result["available"] is True
    assert result["authority"] == "LIVE_ATTENTION_TRIPWIRE"
    assert result["bullish"] is True
    assert result["fresh_flip"] is True
    assert 0 <= result["last_flip_age_seconds"] <= 180
    assert result["volume_acceleration_30s"] is not None
    assert result["dollar_flow_acceleration_30s"] is not None


def test_30s_flip_expires_from_tripwire_without_forcing_bearish_state():
    start = datetime(2026, 9, 8, 18, 58, 0, tzinfo=timezone.utc)
    rows = _annotated_sequence(start)
    scan_time = start + timedelta(minutes=7)

    result = gs396.tripwire_from_annotated(rows, scan_time)

    assert result["bullish"] is True
    assert result["fresh_flip"] is False
    assert result["last_flip_age_seconds"] > 180


def test_entry_authority_strips_live_30s_flip_but_preserves_legacy_1m_signal():
    record = {
        "symbol": "GCDT",
        "supertrend_30s_available": True,
        "supertrend_30s_bullish": True,
        "supertrend_30s_flip": True,
        "supertrend_30s_flip_age_seconds": 25.0,
        "supertrend_flip": False,
        "supertrend_bullish": False,
    }

    entry_view = gs396.entry_authority_record(record)

    assert "supertrend_30s_flip" not in entry_view
    assert "supertrend_30s_flip_age_seconds" not in entry_view
    assert entry_view["supertrend_flip"] is False
    assert entry_view["supertrend_bullish"] is False
    # Source evidence remains untouched for the attention path.
    assert record["supertrend_30s_flip"] is True


def test_install_promotes_real_30s_state_only_to_30s_trend_ladder():
    gs396.install()

    assert getattr(scanner_v2.apply_scanner_v2, "_gs396_live_30s_tripwire", False)
    assert getattr(scanner_v2.trigger_diagnostics, "_gs396_1m_entry_authority", False)

    bullish = {
        "supertrend_30s_available": True,
        "supertrend_30s_bullish": True,
        "supertrend_30s_flip": True,
    }
    bearish = {
        "supertrend_30s_available": True,
        "supertrend_30s_bullish": False,
    }

    assert scanner_v2._trend_confirmation_passed(bullish, "30s") is True
    assert scanner_v2._supertrend_state(bullish, "30s") == "flipped green"
    assert scanner_v2._trend_confirmation_passed(bearish, "30s") is False
    assert scanner_v2._supertrend_state(bearish, "30s") == "not green"


def test_no_stream_evidence_keeps_legacy_record_unchanged():
    record = {"symbol": "SST", "supertrend_flip": True, "supertrend_bullish": True}
    assert gs396.entry_authority_record(record) is record
