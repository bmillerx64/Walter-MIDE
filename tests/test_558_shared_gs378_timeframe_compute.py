"""GS558: scan-local GS378 compute reuse preserves behavior."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs558_shared_gs378_timeframe_compute as gs558


ROOT = Path(__file__).resolve().parents[1]


def test_gs558_reuses_exact_same_objects_inside_apply_only(monkeypatch):
    counts = {
        "supertrend": 0,
        "frame": 0,
        "vwap": 0,
    }

    def fake_supertrend(frame, period=10, multiplier=3.0):
        counts["supertrend"] += 1
        return ("line", "trend", id(frame), period, multiplier)

    def fake_frame(day, label):
        counts["frame"] += 1
        return {"day_id": id(day), "label": label}

    def fake_vwap(series, label):
        counts["vwap"] += 1
        return {"series_id": id(series), "label": label}

    frame = object()
    series = object()
    day = object()

    def fake_apply(records, current_session_raw, current_session_30s_raw, client):
        first_st = gs378.supertrend(frame, 10, 3)
        second_st = gs378.supertrend(frame, 10, 3)
        first_frame = gs378._timeframe_frame(day, "3m")
        second_frame = gs378._timeframe_frame(day, "3m")
        first_vwap = gs378._timeframe_vwap(series, "3m")
        second_vwap = gs378._timeframe_vwap(series, "3m")
        assert first_st is second_st
        assert first_frame is second_frame
        assert first_vwap is second_vwap
        return list(records)

    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    monkeypatch.setattr(gs378, "_timeframe_frame", fake_frame)
    monkeypatch.setattr(gs378, "_timeframe_vwap", fake_vwap)
    monkeypatch.setattr(gs378, "apply_live_vwap_truth", fake_apply)

    client = SimpleNamespace(diagnostics={})
    assert gs558.install() is True

    result = gs378.apply_live_vwap_truth(
        [{"symbol": "TEST"}],
        {},
        {},
        client,
    )

    assert result == [{"symbol": "TEST"}]
    assert counts == {"supertrend": 1, "frame": 1, "vwap": 1}
    trace = client.diagnostics[gs558.DIAGNOSTIC_KEY]
    assert trace["supertrend_requests"] == 2
    assert trace["supertrend_hits"] == 1
    assert trace["supertrend_misses"] == 1
    assert trace["timeframe_frame_hits"] == 1
    assert trace["timeframe_vwap_hits"] == 1
    assert trace["extra_provider_calls"] == 0
    assert trace["trading_logic_changed"] is False
    assert gs558.install() is False


def test_gs558_cache_does_not_cross_apply_boundaries(monkeypatch):
    calls = {"supertrend": 0}
    frame = object()

    def fake_supertrend(frame_obj, period=10, multiplier=3.0):
        calls["supertrend"] += 1
        return calls["supertrend"]

    def fake_apply(records, current_session_raw, current_session_30s_raw, client):
        a = gs378.supertrend(frame, 10, 3)
        b = gs378.supertrend(frame, 10, 3)
        assert a == b
        return records

    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    monkeypatch.setattr(gs378, "apply_live_vwap_truth", fake_apply)

    client = SimpleNamespace(diagnostics={})
    gs558.install()

    gs378.apply_live_vwap_truth([], {}, {}, client)
    gs378.apply_live_vwap_truth([], {}, {}, client)

    assert calls["supertrend"] == 2


def test_gs558_app_installs_after_gs557_hotspot_observer():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    gs557_pos = source.index("mide.gs557_analyze_candidates_hotspots")
    gs558_pos = source.index("mide.gs558_shared_gs378_timeframe_compute")
    participation_pos = source.index("    def participation(records):")

    assert gs557_pos < gs558_pos < participation_pos
    assert ").install()" in source[gs558_pos:gs558_pos + 300]


def test_gs558_scope_is_local_compute_reuse_only():
    source = (
        ROOT / "mide/gs558_shared_gs378_timeframe_compute.py"
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
