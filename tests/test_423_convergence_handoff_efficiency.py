from types import SimpleNamespace

import pandas as pd

from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs421_multitimeframe_convergence_recorder as gs421
from mide import gs422_convergence_recorder_performance as gs422
from mide import gs423_convergence_handoff_efficiency as gs423
from mide.flight_recorder import FlightRecorder


def _day(rows=240):
    index = pd.date_range(
        "2026-09-10 13:30:00+00:00", periods=rows, freq="min"
    )
    close = pd.Series([4.0 + i * 0.002 for i in range(rows)], index=index)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": [1000 + i * 20 for i in range(rows)],
        },
        index=index,
    )


def test_confirmation_metadata_reuses_the_four_existing_supertrend_passes(monkeypatch):
    day = gs378._eastern_day(_day())
    primary = pd.Series(4.0, index=day.index)
    calls = []

    def fake_supertrend(frame, period, multiplier):
        calls.append(len(frame))
        line = pd.Series(3.9, index=frame.index, dtype=float)
        trend = pd.Series(False, index=frame.index, dtype=bool)
        trend.iloc[-2:] = True
        return line, trend

    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    count, details = gs423.confirmation_details_with_maturation(day, primary)

    assert len(calls) == 4
    assert set(details) == {"1m", "3m", "5m", "10m"}
    assert count == 4
    for detail in details.values():
        assert detail["above_vwap"] is True
        assert detail["supertrend"] is True
        assert detail["current_confirmed"] is True
        assert detail["bullish_flip_timestamp"] is not None


def test_maturation_reuses_fast_timeframes_and_computes_only_15m(monkeypatch):
    day = gs378._eastern_day(_day())
    primary = pd.Series(4.0, index=day.index)
    record = {
        "symbol": "TNON",
        "status": "PASS",
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "timeframes": {
            label: {
                "timeframe": label,
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
                "current_confirmed": True,
                "bullish_flip_timestamp": day.index[20 + offset].isoformat(),
                "bullish_flip_age_seconds": 60.0,
                "price_at_flip": 4.10 + offset * 0.01,
            }
            for offset, label in enumerate(("1m", "3m", "5m", "10m"))
        },
    }
    calls = []

    monkeypatch.setattr(
        gs378,
        "primary_vwap_context",
        lambda frame: {"day": day, "series": primary, "value": 4.0},
    )
    monkeypatch.setattr(
        gs421,
        "_timeframe_event",
        lambda _day, _primary, label: (
            calls.append(label)
            or {
                "timeframe": label,
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": True,
                "current_confirmed": True,
                "bullish_flip_timestamp": day.index[30].isoformat(),
                "bullish_flip_age_seconds": 60.0,
                "price_at_flip": 4.2,
            }
        ),
    )

    client = SimpleNamespace(bars_frame=lambda raw: _day())
    evidence = gs423.build_efficient_maturation_evidence(record, [{}], client)

    assert calls == ["15m"]
    assert evidence["reused_supertrend_timeframes"] == ["1m", "3m", "5m", "10m"]
    assert evidence["additional_supertrend_timeframes"] == ["15m"]
    assert evidence["additional_history_requests"] == 0
    assert evidence["authority"] == "OBSERVATIONAL_ONLY"
    assert evidence["entry_authority_changed"] is False


def test_install_owns_final_apply_boundary_even_with_inherited_gs421_marker(monkeypatch):
    calls = []

    def base(records, current_session_raw, current_session_30s_raw, client):
        calls.append("base")
        return records

    def stale_gs421(records, current_session_raw, current_session_30s_raw, client):
        raise AssertionError("stale GS421 wrapper must be replaced, not stacked")

    stale_gs421._gs421_multitimeframe_convergence = True
    stale_gs421._gs421_original = base
    monkeypatch.setattr(gs378, "apply_live_vwap_truth", stale_gs421)
    monkeypatch.setattr(gs422, "should_record_maturation", lambda record: False)

    gs423.install()
    result = gs378.apply_live_vwap_truth(
        [{"symbol": "QUIET", "status": "PASS"}], {"QUIET": []}, {}, SimpleNamespace(diagnostics={})
    )

    assert calls == ["base"]
    assert result[0]["multitimeframe_maturation"]["skipped"] is True
    assert getattr(gs378.apply_live_vwap_truth, "_gs423_convergence_handoff_efficiency") is True


def test_production_flight_recorder_persists_maturation_from_final_record(tmp_path):
    recorder = FlightRecorder(path=tmp_path / "flight.jsonl")
    maturation = {
        "authority": "OBSERVATIONAL_ONLY",
        "available": True,
        "observed_cascade": ["1m", "3m", "5m"],
        "highest_observed_maturation": "5m",
    }
    record = {
        "symbol": "TNON",
        "status": "PASS",
        "candidate_status": "Strengthening",
        "qualified_for_ranking": True,
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "participation_gate": {"passed": True, "checks": []},
        "structure_gate": {"passed": True, "checks": []},
        "trigger_diagnostics": {"trigger": False, "checks": []},
        "multitimeframe_maturation": maturation,
        "multitimeframe_maturation_authority": "OBSERVATIONAL_ONLY",
    }
    settings = SimpleNamespace(
        min_price=0.02,
        max_price=5.0,
        min_pct_change=5.0,
        min_day_volume=100000,
        max_free_float=50000000,
    )
    snapshot = {
        "latestTrade": {"p": 4.39},
        "latestQuote": {"bp": 4.38, "ap": 4.40},
        "dailyBar": {"c": 4.39, "v": 5_000_000},
        "prevDailyBar": {"c": 4.00},
        "free_float": 972_160,
    }

    written = recorder.record_scan(
        seeds=["TNON"],
        discovery_reasons={"TNON": ["DAY_GAINERS"]},
        snapshots={"TNON": snapshot},
        candidates=[{"symbol": "TNON"}],
        analyzed=[dict(record)],
        records=[dict(record)],
        settings=settings,
        scanner_v2=True,
    )

    path = written["symbols"][0]
    assert path["multitimeframe_maturation"] == maturation
    assert path["multitimeframe_maturation"] is not maturation
    assert path["multitimeframe_maturation_authority"] == "OBSERVATIONAL_ONLY"
    assert recorder.latest_scan()["symbols"][0]["multitimeframe_maturation"] == maturation


def test_startup_installs_gs423_last_and_safety_contract_is_unchanged():
    startup = open("mide/startup.py", encoding="utf-8").read()
    source = open("mide/gs423_convergence_handoff_efficiency.py", encoding="utf-8").read()

    assert startup.index("install_late_chain()") < startup.index("install_gs416()")
    assert startup.index("install_gs416()") < startup.index("install_gs423()")
    assert 'record["qualified_for_entry"] =' not in source
    assert "TONE_PATTERNS" not in source
    assert "play_alert" not in source
    assert "client.bars(" not in source
