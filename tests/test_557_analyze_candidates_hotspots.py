"""GS557: analyzer hotspot timing is observational and persistable."""

from pathlib import Path
from types import SimpleNamespace

from mide import discovery
from mide import gs557_analyze_candidates_hotspots as gs557


ROOT = Path(__file__).resolve().parents[1]


def test_gs557_times_existing_calls_without_changing_result(monkeypatch):
    calls = []

    def fake_confirmation(frame):
        calls.append(frame)
        return 1, {"1m": {"above_vwap": True, "supertrend": True}}

    def fake_analyze(client, candidates, news_index, discovery_reasons):
        discovery._timeframe_confirmation("frame")
        return [{"symbol": "TEST", "value": 7}]

    monkeypatch.setattr(discovery, "_timeframe_confirmation", fake_confirmation)
    monkeypatch.setattr(discovery, "analyze_candidates", fake_analyze)
    client = SimpleNamespace(diagnostics={})

    assert gs557.install() is True
    result = discovery.analyze_candidates(client, [{"symbol": "TEST"}], {}, {})

    assert result == [{"symbol": "TEST", "value": 7}]
    assert calls == ["frame"]
    trace = client.diagnostics[gs557.DIAGNOSTIC_KEY]
    assert trace["authority"] == "OBSERVATIONAL_ONLY"
    assert trace["outer_total_ms"] >= 0
    assert trace["extra_provider_calls"] == 0
    row = next(
        item
        for item in trace["functions"]
        if item["function"] == "base.timeframe_confirmation"
    )
    assert row["calls"] == 1


def test_gs557_restores_patched_target_after_exception(monkeypatch):
    original = discovery._timeframe_confirmation

    def broken(_client, _candidates, _news, _reasons):
        raise RuntimeError("synthetic analyzer failure")

    monkeypatch.setattr(discovery, "analyze_candidates", broken)
    client = SimpleNamespace(diagnostics={})

    assert gs557.install() is True
    try:
        discovery.analyze_candidates(client, [], {}, {})
    except RuntimeError as exc:
        assert "synthetic analyzer failure" in str(exc)
    else:
        raise AssertionError("expected synthetic failure")

    assert discovery._timeframe_confirmation is original
    assert gs557.DIAGNOSTIC_KEY in client.diagnostics


def test_gs557_gs554_payload_can_carry_hotspots():
    source = Path(
        "mide/gs554_participation_latency_breakdown.py"
    ).read_text(encoding="utf-8")

    assert "gs557_analyze_candidates_hotspots" in source
    assert '"analyze_candidates_hotspots"' in source


def test_gs557_app_installs_after_market_evidence_imports():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    bind = source.index("mide.gs557_analyze_candidates_hotspots")
    participation = source.index("    def participation(records):")

    assert bind < participation
    assert ").install()" in source[bind:bind + 250]


def test_gs557_scope_is_observational_only():
    source = (
        ROOT / "mide/gs557_analyze_candidates_hotspots.py"
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
