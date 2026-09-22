from mide import gs527_explosive_30s_surge_watch as gs527


def _record(age=10.0, volume=4.7, dollar=5.0):
    return {
        "symbol": "LHSW",
        "supertrend_30s_bullish": True,
        "supertrend_30s_last_flip_age_seconds": age,
        "volume_acceleration_30s": volume,
        "dollar_flow_acceleration_30s": dollar,
        "timeframe_alignment": {
            "30s": {
                "above_vwap": True,
                "supertrend_bullish": True,
                "supertrend_value": 0.75,
                "vwap_value": 0.74,
            }
        },
        "thirty_second_tripwire": {
            "latest_close": 0.78,
            "last_flip_age_seconds": age,
        },
    }


def _view(state="DEVELOPING"):
    return {
        "state": state,
        "color": "#60a5fa",
        "reason": "Still developing.",
        "next_step": "Wait for confirmation.",
        "attention_provenance": [],
        "evidence": [],
    }


def test_lhsw_like_burst_is_active():
    event = gs527.explosive_30s_surge(_record())
    assert event["active"] is True
    assert event["volume_acceleration_30s"] == 4.7
    assert event["dollar_flow_acceleration_30s"] == 5.0


def test_burst_requires_fresh_flip_and_both_flow_thresholds():
    assert gs527.explosive_30s_surge(_record(age=91))["active"] is False
    assert gs527.explosive_30s_surge(_record(volume=2.9))["active"] is False
    assert gs527.explosive_30s_surge(_record(dollar=2.9))["active"] is False


def test_burst_annotates_without_promoting_state():
    result = gs527.state_with_explosive_30s(lambda _r: _view(), _record())
    assert result["state"] == "DEVELOPING"
    assert result["reason"].startswith("EARLY SURGE WATCH:")
    assert result["explosive_30s_surge"]["authority"] == "OPERATOR_ATTENTION_ONLY"


def test_audio_is_attention_only_and_not_look_now():
    phrase = gs527.explosive_30s_audio_phrase([_record()])
    assert "EARLY SURGE WATCH" in phrase
    assert "Attention only" in phrase
    assert "LOOK NOW" not in phrase
    assert "ENTRY READY" not in phrase


def test_event_order_lifts_burst_above_ordinary_peer(monkeypatch):
    ordinary = {"symbol": "AAA"}
    burst = _record()
    monkeypatch.setattr(gs527, "_attention_band", lambda row: 2 if row.get("symbol") == "LHSW" else 1)
    ordered = gs527.ordered_explosive_30s_records([ordinary, burst], baseline_order=lambda rows: rows)
    assert [row["symbol"] for row in ordered] == ["LHSW", "AAA"]
