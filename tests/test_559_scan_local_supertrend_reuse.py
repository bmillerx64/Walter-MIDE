"""GS559: scan-local semantic SuperTrend reuse preserves results."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from mide import discovery
from mide import gs378_live_vwap_st_crossover as gs378
from mide import timeframe_alignment
from mide import gs559_scan_local_supertrend_reuse as gs559


ROOT = Path(__file__).resolve().parents[1]


def _frame(index):
    values = [1.00, 1.04, 1.02, 1.08, 1.10]
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 0.03 for value in values],
            "low": [value - 0.02 for value in values],
            "close": values,
            "volume": [1000, 1200, 1100, 1500, 1700],
        },
        index=index,
    )


def test_gs559_reuses_equal_ohlc_across_distinct_frames_and_aliases(monkeypatch):
    calls = {"count": 0}

    def fake_supertrend(frame, period=10, multiplier=3.0):
        calls["count"] += 1
        line = pd.Series(
            [float(i) for i in range(len(frame))],
            index=frame.index,
            dtype=float,
        )
        trend = pd.Series(True, index=frame.index, dtype=bool)
        return line, trend

    utc = pd.date_range("2026-09-24 13:30:00+00:00", periods=5, freq="min")
    eastern = utc.tz_convert("America/New_York")
    first = _frame(utc)
    second = _frame(eastern)

    def fake_analyze(client, candidates, news_index, discovery_reasons):
        a_line, a_trend = discovery.supertrend(first, 10, 3)
        b_line, b_trend = gs378.supertrend(second, 10, 3)
        c_line, c_trend = timeframe_alignment.supertrend(second, 10, 3)
        assert a_line.tolist() == b_line.tolist() == c_line.tolist()
        assert a_trend.tolist() == b_trend.tolist() == c_trend.tolist()
        assert a_line.index.equals(first.index)
        assert b_line.index.equals(second.index)
        assert c_line.index.equals(second.index)
        return [{"symbol": "TEST"}]

    monkeypatch.setattr(discovery, "supertrend", fake_supertrend)
    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    monkeypatch.setattr(timeframe_alignment, "supertrend", fake_supertrend)
    monkeypatch.setattr(discovery, "analyze_candidates", fake_analyze)

    client = SimpleNamespace(diagnostics={})
    assert gs559.install() is True

    result = discovery.analyze_candidates(client, [{"symbol": "TEST"}], {}, {})

    assert result == [{"symbol": "TEST"}]
    assert calls["count"] == 1
    trace = client.diagnostics[gs559.DIAGNOSTIC_KEY]
    assert trace["requests"] == 3
    assert trace["hits"] == 2
    assert trace["misses"] == 1
    assert trace["cross_scan_cache"] is False
    assert trace["extra_provider_calls"] == 0


def test_gs559_cache_does_not_survive_next_analyzer_call(monkeypatch):
    calls = {"count": 0}
    frame = _frame(
        pd.date_range("2026-09-24 13:30:00+00:00", periods=5, freq="min")
    )

    def fake_supertrend(frame_obj, period=10, multiplier=3.0):
        calls["count"] += 1
        return (
            pd.Series(1.0, index=frame_obj.index, dtype=float),
            pd.Series(True, index=frame_obj.index, dtype=bool),
        )

    def fake_analyze(client, candidates, news_index, discovery_reasons):
        discovery.supertrend(frame, 10, 3)
        discovery.supertrend(frame.copy(), 10, 3)
        return []

    monkeypatch.setattr(discovery, "supertrend", fake_supertrend)
    monkeypatch.setattr(discovery, "analyze_candidates", fake_analyze)
    client = SimpleNamespace(diagnostics={})
    gs559.install()

    discovery.analyze_candidates(client, [], {}, {})
    discovery.analyze_candidates(client, [], {}, {})

    assert calls["count"] == 2


def test_gs559_gs554_payload_carries_reuse_diagnostics():
    source = (
        ROOT / "mide/gs554_participation_latency_breakdown.py"
    ).read_text(encoding="utf-8")

    assert "gs559_scan_local_supertrend_reuse" in source
    assert '"supertrend_reuse"' in source


def test_gs559_app_installs_after_gs558():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    gs558_pos = source.index("mide.gs558_shared_gs378_timeframe_compute")
    gs559_pos = source.index("mide.gs559_scan_local_supertrend_reuse")
    participation_pos = source.index("    def participation(records):")

    assert gs558_pos < gs559_pos < participation_pos
    assert ").install()" in source[gs559_pos:gs559_pos + 300]


def test_gs559_scope_is_compute_reuse_only():
    source = (
        ROOT / "mide/gs559_scan_local_supertrend_reuse.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        ".bars(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
