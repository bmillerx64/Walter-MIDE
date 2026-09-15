from pathlib import Path

import pandas as pd

from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs397_canonical_30s_tripwire_truth as gs397
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide import gs456_canonical_30s_vwap_cross as gs456


def _thirty_second_frame(periods=70):
    index = pd.date_range(
        "2026-09-15T13:30:00Z", periods=periods, freq="30s"
    )
    return pd.DataFrame(
        {
            "open": [1.0] * periods,
            "high": [1.0] * periods,
            "low": [1.0] * periods,
            "close": [1.0] * periods,
            "volume": [1_000.0] * periods,
        },
        index=index,
    )


def test_30s_truth_uses_walters_vwap_not_webull_display(monkeypatch):
    frame = _thirty_second_frame()

    def deterministic_supertrend(source, period, multiplier):
        # No bullish-state flip is required for this test. The ST line itself moves
        # from below the true VWAP to above it on the final completed 30s bar.
        line = pd.Series([0.90] * (len(source) - 1) + [1.10], index=source.index)
        trend = pd.Series([True] * len(source), index=source.index)
        return line, trend

    monkeypatch.setattr(gs378, "supertrend", deterministic_supertrend)
    truth = gs456.alignment_30s_truth(frame)

    assert truth["vwap_value"] == 1.0
    assert truth["vwap_anchor_mode"] == "RTH_09:30_ET"
    assert truth["above_vwap"] is True
    assert truth["supertrend_value"] == 1.1
    assert truth["authority"] == gs456.AUTHORITY

    cross = truth["st_vwap_line_cross"]
    assert cross["crossed"] is True
    assert cross["current_confirmed"] is True
    assert cross["new"] is True
    assert cross["vwap_value"] == 1.0
    assert cross["supertrend_value"] == 1.1


def test_30s_line_cross_is_distinct_from_supertrend_state_flip(monkeypatch):
    frame = _thirty_second_frame()

    def deterministic_supertrend(source, period, multiplier):
        line = pd.Series([0.90] * (len(source) - 1) + [1.10], index=source.index)
        # Bullish throughout: there is no bearish->bullish SuperTrend state flip.
        trend = pd.Series([True] * len(source), index=source.index)
        return line, trend

    monkeypatch.setattr(gs378, "supertrend", deterministic_supertrend)
    truth = gs456.alignment_30s_truth(frame)
    assert truth["supertrend_bullish"] is True
    assert truth["st_vwap_line_cross"]["crossed"] is True


def test_gs397_prefers_canonical_30s_vwap_over_broader_stage6_vwap():
    old_above = gs397._primary_above_vwap
    old_canonicalize = gs397.canonicalize_record
    try:
        gs456._install_gs397_canonicalization()
        result = gs397._primary_above_vwap(
            {"vwap_value": 2.00},
            {
                "authority": gs456.AUTHORITY,
                "vwap_value": 1.00,
                "above_vwap": True,
            },
            {"latest_close": 1.10},
        )
        assert result is True
    finally:
        gs397._primary_above_vwap = old_above
        gs397.canonicalize_record = old_canonicalize


def test_canonicalization_surfaces_numeric_30s_vwap_and_cross_without_entry_change():
    old_above = gs397._primary_above_vwap
    old_canonicalize = gs397.canonicalize_record
    event = {
        "timeframe": "30s",
        "crossed": True,
        "recent": True,
        "new": True,
        "timestamp": "2026-09-15T10:18:00-04:00",
        "age_seconds": 30.0,
        "current_confirmed": True,
    }
    record = {
        "symbol": "RETO",
        "vwap_value": 9.99,
        "qualified_for_entry": False,
        "qualified_for_watch": False,
        "supertrend_30s_available": True,
        "supertrend_30s_bullish": True,
        "thirty_second_tripwire": {"latest_close": 0.70},
        "timeframe_alignment": {
            "30s": {
                "authority": gs456.AUTHORITY,
                "source": gs456.SOURCE,
                "above_vwap": True,
                "supertrend_bullish": True,
                "aligned": False,
                "vwap_value": 0.62,
                "vwap_anchor_mode": "RTH_09:30_ET",
                "vwap_anchor_time_et": "2026-09-15T09:30:00-04:00",
                "supertrend_value": 0.64,
                "st_vwap_line_cross": event,
            }
        },
        "timeframes": {},
        "alignment_score": 0,
    }

    try:
        gs456._install_gs397_canonicalization()
        updated = gs397.canonicalize_record(record)
        assert updated["vwap_30s_value"] == 0.62
        assert updated["vwap_30s_anchor_mode"] == "RTH_09:30_ET"
        assert updated["st_vwap_30s_line_cross"] == event
        assert updated["timeframes"]["30s"]["vwap_value"] == 0.62
        assert updated["qualified_for_entry"] is False
        assert updated["qualified_for_watch"] is False
    finally:
        gs397._primary_above_vwap = old_above
        gs397.canonicalize_record = old_canonicalize


def test_gs455_first_rung_prefers_literal_30s_cross_and_falls_back_to_tripwire():
    old_rung = gs455._thirty_second_rung
    try:
        gs456._install_gs455_first_rung()
        literal = gs455._thirty_second_rung(
            {
                "st_vwap_30s_line_cross": {
                    "timeframe": "30s",
                    "crossed": True,
                    "recent": True,
                    "new": True,
                    "timestamp": "2026-09-15T10:18:00-04:00",
                    "age_seconds": 20.0,
                    "current_confirmed": True,
                },
                "supertrend_30s_bullish": True,
                "supertrend_30s_last_flip_timestamp": "2026-09-15T10:17:00-04:00",
                "supertrend_30s_last_flip_age_seconds": 80.0,
            }
        )
        assert literal["kind"] == "literal_30s_st_vwap_line_cross"
        assert literal["timestamp"] == "2026-09-15T10:18:00-04:00"

        fallback = gs455._thirty_second_rung(
            {
                "supertrend_30s_bullish": True,
                "supertrend_30s_last_flip_timestamp": "2026-09-15T10:17:00-04:00",
                "supertrend_30s_last_flip_age_seconds": 80.0,
            }
        )
        assert "tripwire" in fallback["kind"]
        assert fallback["crossed"] is True
    finally:
        gs455._thirty_second_rung = old_rung


def test_gs456_chains_after_gs455_on_cold_and_warm_runtime_paths():
    source = Path("mide/gs454_flight_recorder_download_freshness.py").read_text(
        encoding="utf-8"
    )
    assert "gs456_canonical_30s_vwap_cross" in source
    assert source.count("_install_gs456()") >= 2


def test_gs456_scope_lock_adds_no_provider_or_entry_authority():
    source = Path("mide/gs456_canonical_30s_vwap_cross.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "stream_30s_bars(",
        ".bars(",
        "qualified_for_entry =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    for token in forbidden:
        assert token not in source
    assert "primary_vwap_context" in source
    assert "st_vwap_line_cross" in source
    assert "gs378.supertrend(day, 10, 3)" in source
