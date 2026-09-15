from datetime import datetime, timezone
from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs365_chime_semantic_classifier as chimes
from mide import gs396_live_30s_tripwire as gs396
from mide import gs460_st_flip_compression_ignition as gs460


def _record(
    *,
    p30=2.78,
    p1=2.82,
    p3=2.86,
    p5=2.90,
    a30=60.0,
    a1=90.0,
    a3=180.0,
    a5=300.0,
    volume=250_000,
    vwap_distance_pct=1.5,
):
    return {
        "symbol": "RETO",
        "price": 3.05,
        "volume": volume,
        "vwap_distance_pct": vwap_distance_pct,
        "supertrend_30s_bullish": True,
        "supertrend_30s_last_flip_price": p30,
        "supertrend_30s_last_flip_age_seconds": a30,
        "supertrend_30s_last_flip_timestamp": "2026-09-15T18:09:00+00:00",
        "thirty_second_tripwire": {
            "bullish": True,
            "last_flip_price": p30,
            "last_flip_age_seconds": a30,
            "last_flip_timestamp": "2026-09-15T18:09:00+00:00",
        },
        "timeframes": {
            "1m": {
                "price_at_flip": p1,
                "bullish_flip_age_seconds": a1,
                "bullish_flip_timestamp": "2026-09-15T18:10:00+00:00",
                "current_supertrend_bullish": True,
                "current_close": 3.05,
                "st_vwap_line_cross": {"latest_supertrend_value": 2.76},
            },
            "3m": {
                "price_at_flip": p3,
                "bullish_flip_age_seconds": a3,
                "bullish_flip_timestamp": "2026-09-15T18:11:00+00:00",
                "current_supertrend_bullish": True,
                "current_close": 3.05,
                "st_vwap_line_cross": {"latest_supertrend_value": 2.84},
            },
            "5m": {
                "price_at_flip": p5,
                "bullish_flip_age_seconds": a5,
                "bullish_flip_timestamp": "2026-09-15T18:12:00+00:00",
                "current_supertrend_bullish": True,
                "current_close": 3.05,
                "st_vwap_line_cross": {"latest_supertrend_value": 2.91},
            },
            "10m": {
                "current_supertrend_bullish": False,
                "current_close": 3.05,
                "st_vwap_line_cross": {"latest_supertrend_value": 3.10},
            },
        },
        "multitimeframe_maturation": {
            "timeframes": {
                "15m": {
                    "current_supertrend_bullish": False,
                    "current_close": 3.05,
                    "st_vwap_line_cross": {"latest_supertrend_value": 3.18},
                }
            }
        },
    }


def test_reto_like_bottom_up_flip_prices_form_ignition_cascade():
    signal = gs460.st_flip_compression(_record())

    assert signal["active"] is True
    assert signal["depth"] == 4
    assert signal["stage"] == "IGNITION CASCADE"
    assert signal["sequence"] == "30s -> 1m -> 3m -> 5m"
    assert signal["cluster_span_pct"] < signal["cluster_limit_pct"]
    assert signal["supporting_flow"] is True
    assert signal["authority"] == "OPERATOR_ATTENTION_ONLY"
    assert signal["entry_authority_changed"] is False
    assert signal["next_frame"]["timeframe"] == "10m"


def test_compression_starts_at_30s_and_does_not_backfill_from_slower_frames():
    record = _record()
    record["supertrend_30s_last_flip_price"] = None
    record["thirty_second_tripwire"]["last_flip_price"] = None

    signal = gs460.st_flip_compression(record)
    assert signal["depth"] == 0
    assert signal["active"] is False


def test_two_rung_early_ignition_is_allowed_before_slower_frames_join():
    record = _record()
    record["timeframes"]["3m"]["current_supertrend_bullish"] = False

    signal = gs460.st_flip_compression(record)
    assert signal["active"] is True
    assert signal["depth"] == 2
    assert signal["stage"] == "EARLY IGNITION"
    assert signal["sequence"] == "30s -> 1m"
    assert signal["next_frame"]["timeframe"] == "3m"


def test_far_apart_flip_prices_are_not_compression():
    signal = gs460.st_flip_compression(_record(p30=2.40, p1=2.82))
    assert signal["depth"] >= 2
    assert signal["cluster_span_pct"] > signal["cluster_limit_pct"]
    assert signal["active"] is False


def test_compression_requires_buy_in_flow_support():
    record = _record(volume=0)
    record.update(
        {
            "participation_score": 0,
            "participation_surge_score": 0,
            "expansion_quality": 0,
            "expansion_score": 0,
            "volume_acceleration": 0,
            "dollar_flow_acceleration": 0,
            "dollar_flow_acceleration_5m": 0,
            "headline": "",
            "fresh_news": False,
            "news_catalyst": False,
            "has_catalyst": False,
            "catalyst_confirmed": False,
        }
    )
    signal = gs460.st_flip_compression(record)
    assert signal["supporting_flow"] is False
    assert signal["active"] is False


def test_signal_is_session_agnostic_so_premarket_can_build_attention_evidence():
    record = _record()
    record["market_phase"] = "Pre-Market"
    record["regular_market_open"] = False

    signal = gs460.st_flip_compression(record)
    assert signal["active"] is True
    assert signal["entry_authority_changed"] is False


def test_compression_promotes_look_now_but_preserves_anti_chase():
    normal = gs460._state_with_compression(
        lambda _record: {
            "state": unified.DEVELOPING,
            "color": unified.STATE_COLORS[unified.DEVELOPING],
            "reason": "base",
            "next_step": "base",
        },
        _record(vwap_distance_pct=1.5),
    )
    assert normal["state"] == unified.LOOK_NOW
    assert "IGNITION CASCADE" in normal["reason"]
    assert "does not grant entry authority" in normal["next_step"]

    extended = gs460._state_with_compression(
        lambda _record: {
            "state": unified.DEVELOPING,
            "color": unified.STATE_COLORS[unified.DEVELOPING],
            "reason": "base",
            "next_step": "base",
        },
        _record(vwap_distance_pct=7.0),
    )
    assert extended["state"] == unified.CHASE_WAIT
    assert "DO NOT CHASE" in extended["next_step"]


def test_fresh_join_uses_existing_distinct_look_now_audio_semantics():
    # 5m is still inside GS460's new-rung audio window.
    record = _record(a5=120.0)
    signal = gs460.st_flip_compression(record)
    assert signal["fresh_join"] is True

    phrase = gs460._compression_phrase([record])
    assert "LOOK NOW" in phrase
    assert "Ignition compression" in phrase
    # Existing GS392/GS399 broker makes tier 2 acoustically distinct from routine.
    assert chimes.semantic_chime_count(phrase) == 2


def test_30s_tripwire_retains_actual_flip_price_without_entry_authority_change():
    rows = [
        {
            "supertrend_ready": True,
            "supertrend_state": "bearish",
            "timestamp_ms": 1_789_496_900_000,
            "close": 2.70,
            "volume": 10_000,
            "supertrend_10_3": 2.80,
        },
        {
            "supertrend_ready": True,
            "supertrend_state": "bullish",
            "timestamp_ms": 1_789_496_930_000,
            "close": 2.78,
            "volume": 25_000,
            "supertrend_10_3": 2.68,
        },
        {
            "supertrend_ready": True,
            "supertrend_state": "bullish",
            "timestamp_ms": 1_789_496_960_000,
            "close": 2.84,
            "volume": 30_000,
            "supertrend_10_3": 2.72,
        },
    ]
    scan_time = datetime.fromtimestamp(1_789_497_000, tz=timezone.utc)
    tripwire = gs396.tripwire_from_annotated(rows, scan_time)

    assert tripwire["last_flip_price"] == 2.78
    view = gs396.entry_authority_record(
        {
            "supertrend_30s_available": True,
            "supertrend_30s_flip": True,
            "supertrend_30s_last_flip_price": 2.78,
            "qualified_for_entry": False,
        }
    )
    assert "supertrend_30s_flip" not in view
    assert view["supertrend_30s_last_flip_price"] == 2.78
    assert view["qualified_for_entry"] is False


def test_gs460_installs_after_gs459_before_final_order():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs460_st_flip_compression_ignition" in source
    assert source.index("install_gs459()") < source.index("install_gs460()")
    assert source.index("install_gs460()") < source.index("install_final_order()")


def test_gs460_scope_lock_keeps_execution_and_provider_authority_unchanged():
    source = Path("mide/gs460_st_flip_compression_ignition.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "get_bars(",
        "history(",
        "stream_30s_bars(",
        "TRIGGER_",
        "PARTICIPATION_MIN_",
    )
    for token in forbidden:
        assert token not in source
    assert "OPERATOR_ATTENTION_ONLY" in source
    assert "30s -> 1m -> 3m -> 5m" in source
