from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs459_price_trajectory_attention as gs459
from mide import gs462_preflip_ignition_watch as gs462


def _record(*, one_bullish=True, one_gap=None, three_bullish=False, three_gap=None, flow=True):
    price = 2.00

    def tf(bullish, gap):
        st = price * (1.0 + gap / 100.0) if gap is not None else (1.90 if bullish else 2.20)
        return {
            "current_supertrend_bullish": bullish,
            "current_above_vwap": True,
            "current_close": price,
            "current_vwap": 1.95,
            "st_vwap_line_cross": {
                "latest_supertrend_value": st,
                "latest_vwap_value": 1.95,
            },
        }

    return {
        "symbol": "TEST",
        "price": price,
        "supertrend_30s_bullish": True,
        "supertrend_30s_last_flip_age_seconds": 60.0,
        "timeframe_alignment": {
            "30s": {
                "above_vwap": True,
                "supertrend_bullish": True,
                "supertrend_value": 1.90,
                "vwap_value": 1.94,
            }
        },
        "thirty_second_tripwire": {"latest_close": price, "last_flip_age_seconds": 60.0},
        "timeframes": {
            "1m": tf(one_bullish, one_gap),
            "3m": tf(three_bullish, three_gap),
            "5m": tf(False, 4.0),
            "10m": tf(False, 6.0),
        },
        "_test_flow": flow,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }


def _patch_flow(monkeypatch):
    monkeypatch.setattr(gs459, "_supporting_flow", lambda record: bool(record.get("_test_flow")))


def test_recent_30s_flip_plus_green_1m_above_vwap_is_early_watch_without_3m(monkeypatch):
    _patch_flow(monkeypatch)
    signal = gs462.preflip_ignition_watch(_record(one_bullish=True, three_bullish=False, three_gap=5.0))

    assert signal["active"] is True
    assert signal["stage"] == "EARLY WATCH"
    assert signal["jet_fuel"] is False
    assert signal["three_minute_required_for_watch"] is False
    assert signal["five_ten_required"] is False


def test_one_minute_can_be_near_instead_of_already_green(monkeypatch):
    _patch_flow(monkeypatch)
    signal = gs462.preflip_ignition_watch(_record(one_bullish=False, one_gap=1.5))

    assert signal["active"] is True
    assert signal["one_minute"]["near_supertrend"] is True
    assert abs(signal["one_minute"]["st_gap_pct"] - 1.5) < 0.01
    assert signal["near_st_line_limit_pct"] == 2.0


def test_one_minute_gap_outside_provisional_band_does_not_create_watch(monkeypatch):
    _patch_flow(monkeypatch)
    signal = gs462.preflip_ignition_watch(_record(one_bullish=False, one_gap=2.5))

    assert signal["active"] is False
    assert signal["one_minute"]["near_supertrend"] is False


def test_vwap_is_required_for_both_30s_and_1m(monkeypatch):
    _patch_flow(monkeypatch)
    record = _record()
    record["timeframe_alignment"]["30s"]["above_vwap"] = False
    assert gs462.preflip_ignition_watch(record)["active"] is False

    record = _record()
    record["timeframes"]["1m"]["current_above_vwap"] = False
    assert gs462.preflip_ignition_watch(record)["active"] is False


def test_three_minute_support_plus_flow_is_jet_fuel_not_watch_gate(monkeypatch):
    _patch_flow(monkeypatch)
    signal = gs462.preflip_ignition_watch(
        _record(one_bullish=True, three_bullish=False, three_gap=1.2, flow=True)
    )

    assert signal["active"] is True
    assert signal["jet_fuel"] is True
    assert signal["stage"] == "JET FUEL"
    assert signal["three_minute"]["near_supertrend"] is True


def test_three_minute_without_flow_remains_early_watch(monkeypatch):
    _patch_flow(monkeypatch)
    signal = gs462.preflip_ignition_watch(
        _record(one_bullish=True, three_bullish=True, flow=False)
    )

    assert signal["active"] is True
    assert signal["jet_fuel"] is False
    assert signal["stage"] == "EARLY WATCH"


def test_five_and_ten_minute_are_bonus_only(monkeypatch):
    _patch_flow(monkeypatch)
    record = _record(one_bullish=True, three_bullish=True, flow=True)
    record["timeframes"]["5m"]["current_supertrend_bullish"] = True
    record["timeframes"]["5m"]["current_above_vwap"] = True
    record["timeframes"]["10m"]["current_supertrend_bullish"] = True
    record["timeframes"]["10m"]["current_above_vwap"] = True

    signal = gs462.preflip_ignition_watch(record)
    assert signal["active"] is True
    assert signal["jet_fuel"] is True
    assert signal["bonus_continuation"] == ["5m", "10m"]
    assert signal["five_ten_required"] is False


def test_state_enrichment_does_not_rewrite_opportunity_state_or_authority(monkeypatch):
    _patch_flow(monkeypatch)
    record = _record(one_bullish=False, one_gap=1.0, three_bullish=False, three_gap=1.0, flow=True)
    base = {
        "state": unified.DEVELOPING,
        "reason": "Base developing reason.",
        "next_step": "Keep watching.",
        "attention_provenance": [],
    }

    view = gs462._state_with_preflip(lambda _row: dict(base), record)
    assert view["state"] == unified.DEVELOPING
    assert "EARLY ST WATCH:" in view["reason"]
    assert "JET FUEL:" in view["reason"]
    assert "3m adds jet fuel; 5m/10m are bonuses, not gates" in view["next_step"]
    assert record["qualified_for_entry"] is False
    assert record["qualified_for_alert"] is False


def test_preflip_watch_sits_below_real_look_now_band(monkeypatch):
    _patch_flow(monkeypatch)
    record = _record(one_bullish=True)
    monkeypatch.setattr(gs459, "effective_attention_band", lambda _record: 30)
    assert gs462.effective_attention_band(record) == 39

    monkeypatch.setattr(gs459, "effective_attention_band", lambda _record: 40)
    assert gs462.effective_attention_band(record) == 40


def test_gs462_is_reasserted_at_final_presentation_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs462_preflip_ignition_watch" in source
    assert "_install_gs462()" in source
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    assert startup.index("install_gs461()") < startup.index("install_final_order()")


def test_gs462_scope_lock_is_attention_only_and_adds_no_audio_or_provider_work():
    source = Path("mide/gs462_preflip_ignition_watch.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "escalation_alert_phrase",
        "semantic_chime_count",
    )
    for token in forbidden:
        assert token not in source
    assert "NEAR_ST_LINE_PCT = 2.0" in source
    assert "PRE_FLIP_ATTENTION_BAND = 39" in source
