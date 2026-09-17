from pathlib import Path

from mide import gs484_fmp_transport_truth as gs484


class Provider:
    def __init__(self, metrics):
        self.diagnostics = {"news_coverage": metrics}


def test_successful_empty_fmp_fetch_is_distinguishable_from_failure():
    provider = Provider({
        "active_provider": "Financial Modeling Prep news",
        "query_since": "2026-09-17T17:00:00+00:00",
        "effective_provider_since": "2026-09-17T17:00:00+00:00",
        "provider_endpoints": ["news/stock", "news/press-releases"],
        "requests_made": 4,
        "articles_received": 0,
        "provider_failures": 0,
        "request_latency_ms": [121.5, 144.0],
        "requested_symbols": ["PAAI", "SDST"],
        "symbols_with_articles": [],
        "symbols_without_articles": ["PAAI", "SDST"],
        "newest_articles_by_symbol": {
            "PAAI": {"articles_returned": 0, "newest_article_at": None},
        },
    })

    truth = gs484.transport_truth(provider)

    assert truth["metrics_present"] is True
    assert truth["fmp_active"] is True
    assert truth["transport_disposition"] == "SUCCESS_EMPTY"
    assert truth["requests_made"] == 4
    assert truth["articles_received"] == 0
    assert truth["provider_endpoints"] == ["news/stock", "news/press-releases"]
    assert truth["requested_symbols"] == ["PAAI", "SDST"]
    assert truth["symbols_without_articles"] == ["PAAI", "SDST"]
    assert truth["request_latency_last_ms"] == 144.0
    assert truth["extra_provider_calls"] == 0
    assert truth["trading_authority_changed"] is False


def test_failure_trace_keeps_class_and_status_but_never_raw_secret_or_url():
    secret = "SUPER_SECRET_KEY"
    provider = Provider({
        "active_provider": "None",
        "requests_made": 2,
        "articles_received": 0,
        "provider_failures": 1,
        "provider_failure_diagnostics": [{
            "provider": "Financial Modeling Prep news",
            "operation": "fetch news",
            "exception": (
                "HTTPError: 403 Client Error for url: "
                f"https://example.invalid/news/stock?apikey={secret}&symbols=PAAI"
            ),
            "affected_symbols": ["PAAI"],
            "recovery_action": "try next provider; preserve cached news",
        }],
    })

    truth = gs484.transport_truth(provider)
    rendered = repr(truth)

    assert truth["transport_disposition"] == "PROVIDER_FAILURE"
    assert truth["failure_tail"][0]["exception_type"] == "HTTPError"
    assert truth["failure_tail"][0]["http_status"] == 403
    assert truth["failure_tail"][0]["affected_symbol_count"] == 1
    assert truth["failure_tail"][0]["raw_exception_persisted"] is False
    assert secret not in rendered
    assert "example.invalid" not in rendered
    assert "apikey" not in rendered.lower()


def test_newest_article_timestamp_is_observed_without_story_body():
    provider = Provider({
        "active_provider": "Financial Modeling Prep news",
        "requests_made": 2,
        "articles_received": 2,
        "newest_articles_by_symbol": {
            "AAA": {"newest_article_at": "2026-09-17T18:00:00+00:00"},
            "BBB": {"newest_article_at": "2026-09-17T18:03:00+00:00"},
        },
    })

    truth = gs484.transport_truth(provider)

    assert truth["transport_disposition"] == "SUCCESS_WITH_ARTICLES"
    assert truth["newest_returned_article_at"] == "2026-09-17T18:03:00+00:00"


def test_install_enriches_gs481_news_truth_without_fetching(monkeypatch):
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs481_live_evidence_hard_bind as gs481

    provider = Provider({
        "active_provider": "Financial Modeling Prep news",
        "requests_made": 1,
        "articles_received": 0,
    })
    original = gs481._news_truth
    monkeypatch.setattr(gs481, "_news_truth", lambda: {"selected_count": 0})
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "test-provider"))

    gs484.install()
    result = gs481._news_truth()

    assert result["selected_count"] == 0
    assert result["gs484_transport_truth"] is True
    assert result["transport"]["active_provider"] == "Financial Modeling Prep news"
    assert result["transport"]["provider_source"] == "test-provider"
    assert result["transport"]["extra_provider_calls"] == 0

    monkeypatch.setattr(gs481, "_news_truth", original)


def test_app_entry_and_late_startup_install_gs484_after_gs481():
    app = Path("app.py").read_text(encoding="utf-8")
    startup = Path("mide/startup.py").read_text(encoding="utf-8")

    app_481 = app.index("_install_gs481_live_evidence()")
    app_484 = app.index("_install_gs484_fmp_transport_truth()")
    assert app_481 < app_484

    body = startup.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert "gs484_fmp_transport_truth" in body
    assert body.index("install_gs481()") < body.index("install_gs484()") < body.index("install_gs483()")


def test_scope_lock_is_observability_only():
    source = Path("mide/gs484_fmp_transport_truth.py").read_text(encoding="utf-8")

    assert "extra_provider_calls\": 0" in source
    assert "trading_authority_changed\": False" in source
    assert ".get(" in source
    assert "session.get(" not in source
    assert "requests.get(" not in source
    assert "qualified_for_entry" not in source
    assert "qualified_for_alert" not in source
    assert "submit_order" not in source
