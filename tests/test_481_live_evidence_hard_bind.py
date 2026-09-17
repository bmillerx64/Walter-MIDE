from pathlib import Path

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs480_catalyst_story_intelligence as gs480
from mide import gs481_live_evidence_hard_bind as gs481


def test_hard_bind_writes_news_story_trace_and_stream_failure(monkeypatch):
    captured = {}

    def base(recorder, scan, records, *args, **kwargs):
        captured["scan"] = scan
        return scan

    globals_dict = {"persist_replayable_scan": base}

    class Provider:
        _subscription = None
        _subscribed = set()
        diagnostics = {
            "webull_stream": {
                "stream_connection_status": "error",
                "subscription_failures": ["RuntimeError: tick subscription did not confirm"],
                "disconnect_count": 2,
            }
        }

    provider = Provider()
    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: globals_dict)
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "test-provider"))
    monkeypatch.setattr(gs480, "_LATEST_MARKETWIDE_TRACE", [{
        "symbol": "PAAI",
        "headline": "10-year $1B agreement",
        "created_at": "2026-09-17T15:00:00+00:00",
    }])
    monkeypatch.setattr(gs480, "_LATEST_TARGETED_TRACE", {
        "PAAI": {"headline": "10-year $1B agreement", "age_minutes": 1.0}
    })
    monkeypatch.setattr(gs480, "_LAST_SELECTED", [{
        "symbol": "PAAI", "seed_type": "story_material_attention"
    }])

    gs481.install()
    result = globals_dict["persist_replayable_scan"](
        object(), {"scan_id": "scan-481", "recorder_runtime_identity": {}}, []
    )

    assert result["news_story_trace"]["marketwide_count"] == 1
    assert result["news_story_trace"]["targeted_count"] == 1
    assert result["news_story_trace"]["marketwide"][0]["symbol"] == "PAAI"
    failure = result["stream_30s_health"]["failure_diagnostics"]
    assert failure["connection_status"] == "error"
    assert failure["subscription_present"] is False
    assert failure["subscription_failure_count"] == 1
    assert "tick subscription did not confirm" in failure["subscription_failures_tail"][0]
    assert result["live_evidence_hard_bind"]["gs481_hard_bind"] is True
    assert captured["scan"] is result


def test_stream_failure_text_is_sanitized():
    class Provider:
        _subscription = None
        _subscribed = set()
        diagnostics = {
            "webull_stream": {
                "stream_connection_status": "error",
                "subscription_failures": ["Authorization token=do-not-record"],
            }
        }

    truth = gs481._stream_failure_truth(Provider())
    assert truth["subscription_failures_tail"] == [
        "[redacted: potentially sensitive stream failure]"
    ]


def test_startup_installs_gs481_after_gs480_before_scheduler_release():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert "gs481_live_evidence_hard_bind" in source
    assert body.index("install_gs480()") < body.index("install_gs481()") < body.index("install_gs428()")


def test_gs481_scope_lock_is_observability_only():
    source = Path("mide/gs481_live_evidence_hard_bind.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "opportunity_score =",
        "conviction_score =",
        "catalyst_score =",
        "execute_order",
        "place_order",
        ".subscribe(",
        "ensure_stream(",
        "client.bars(",
        "client.snapshots(",
    )
    for token in forbidden:
        assert token not in source
