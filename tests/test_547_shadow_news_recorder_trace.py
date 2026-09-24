"""GS547: persist GS544 Alpaca shadow-news diagnostics for forensic review."""

from copy import deepcopy
from pathlib import Path

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs487_cached_recorder_instance_bind as gs487
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


class Provider:
    def __init__(self, trace=None):
        self.diagnostics = {
            "gs544_alpaca_news_shadow": deepcopy(trace or {}),
            "news_coverage": {
                "active_provider": "Financial Modeling Prep news",
                "provider_endpoints": ["news/stock"],
                "requests_made": 1,
                "articles_received": 0,
                "requested_symbols": ["RAVE"],
                "symbols_without_articles": ["RAVE"],
                "provider_failures": 0,
            },
            "webull_stream": {
                "stream_connection_status": "connected",
                "subscription_failures": [],
                "disconnect_count": 0,
            },
        }
        self._subscription = None
        self._subscribed = set()


def retained_recorder(saved: dict):
    def persist(_recorder, scan, _records, *args, **kwargs):
        saved.update(scan)
        return scan

    namespace = {
        "__name__": "mide.flight_recorder",
        "persist_replayable_scan": persist,
    }
    exec(
        "def record_scan(self, *, scan, records):\n"
        "    return persist_replayable_scan(self, scan, records)\n",
        namespace,
    )

    class RetainedRecorder:
        pass

    RetainedRecorder.record_scan = namespace["record_scan"]
    return RetainedRecorder(), namespace


def shadow_trace():
    return {
        "authority": "NEWS_COVERAGE_OBSERVATION_ONLY",
        "provider_role": "shadow_context_only",
        "requested_missing_symbols": ["RAVE"],
        "query_targets": ["RAVE"],
        "request_made": True,
        "polled_at": "2026-09-24T18:17:00+00:00",
        "articles_received": 1,
        "found_symbols": ["RAVE"],
        "missing_after_shadow": [],
        "articles_by_symbol": {
            "RAVE": {
                "symbol": "RAVE",
                "headline": "RAVE reports record quarterly revenue",
                "created_at": "2026-09-24T14:15:00+00:00",
                "age_minutes_at_poll": 242.0,
                "source": "Benzinga",
                "provider": "Alpaca Market Data",
                "catalyst_score": 3,
                "flags": ["earnings"],
            }
        },
        "coverage_gain_count": 1,
        "trading_authority_changed": False,
        "headline_changed": False,
        "catalyst_score_changed": False,
        "discovery_changed": False,
        "ranking_changed": False,
        "readiness_changed": False,
        "execution_changed": False,
    }


def test_gs547_snapshot_persists_shadow_news_without_mutating_provider():
    trace = shadow_trace()
    provider = Provider(trace)
    before = deepcopy(provider.diagnostics)

    saved = replay_validation.cached_recorder_shadow_news_trace(
        provider,
        "test-provider",
    )

    assert saved["available"] is True
    assert saved["found_symbols"] == ["RAVE"]
    assert saved["articles_by_symbol"]["RAVE"]["source"] == "Benzinga"
    assert saved["provider_source"] == "test-provider"
    assert saved["cached_recorder_instance_bind"] is True
    assert saved["extra_provider_calls"] == 0
    assert saved["trading_authority_changed"] is False
    assert provider.diagnostics == before


def test_gs547_exact_cached_recorder_persists_shadow_news(monkeypatch):
    saved = {}
    recorder, retained_globals = retained_recorder(saved)
    provider = Provider(shadow_trace())
    monkeypatch.setattr(
        gs427,
        "_active_provider",
        lambda: (provider, "retained-test-provider"),
    )

    assert gs487.install_for_recorder(recorder) is True
    recorder.record_scan(
        scan={"scan_id": "gs547"},
        records=[],
    )

    trace = saved["gs544_alpaca_news_shadow"]
    assert trace["available"] is True
    assert trace["found_symbols"] == ["RAVE"]
    assert trace["coverage_gain_count"] == 1
    assert trace["articles_by_symbol"]["RAVE"]["headline"].startswith("RAVE")
    assert saved["recorder_instance_transport_bind"]["revision"] == 2
    assert getattr(
        retained_globals["persist_replayable_scan"],
        gs487._OWNER,
    ) == 2


def test_gs547_unavailable_shadow_trace_is_explicit(monkeypatch):
    saved = {}
    recorder, _ = retained_recorder(saved)
    provider = Provider({})
    monkeypatch.setattr(
        gs427,
        "_active_provider",
        lambda: (provider, "test-provider"),
    )

    assert gs487.install_for_recorder(recorder) is True
    recorder.record_scan(
        scan={"scan_id": "no-shadow"},
        records=[],
    )

    trace = saved["gs544_alpaca_news_shadow"]
    assert trace["available"] is False
    assert trace["reason"] == "GS544 shadow-news diagnostics unavailable"
    assert trace["extra_provider_calls"] == 0


def test_gs547_revision_two_replaces_prior_gs487_wrapper_cleanly(monkeypatch):
    saved = {}
    recorder, retained_globals = retained_recorder(saved)
    original = retained_globals["persist_replayable_scan"]

    def prior_revision(*args, **kwargs):
        return original(*args, **kwargs)

    setattr(prior_revision, gs487._OWNER, 1)
    prior_revision._gs487_original = original
    retained_globals["persist_replayable_scan"] = prior_revision

    monkeypatch.setattr(
        gs427,
        "_active_provider",
        lambda: (Provider(shadow_trace()), "upgrade-test"),
    )

    assert gs487.install_for_recorder(recorder) is True
    current = retained_globals["persist_replayable_scan"]

    assert current is not prior_revision
    assert getattr(current, gs487._OWNER) == gs487.REVISION == 2
    assert current._gs487_original is original


def test_gs547_shadow_persistence_is_observation_only():
    source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    start = source.index("def cached_recorder_shadow_news_trace(")
    end = source.index("def cached_recorder_stream_transport(", start)
    block = source[start:end]

    assert "extra_provider_calls" in block
    assert "trading_authority_changed" in block
    forbidden = (
        ".news(",
        ".fetch(",
        "qualified_for_entry",
        "qualified_for_alert",
        "qualified_for_watch",
        "mission_rank",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)


def test_gs547_compact_bundle_needs_no_special_export_path():
    source = (
        ROOT / "mide/gs510_compact_analysis_bundle.py"
    ).read_text(encoding="utf-8")

    assert '"flight_recorder.jsonl"' in source
    assert "exact captured point-in-time prefix" in source
