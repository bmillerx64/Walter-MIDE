from mide import gs384_diagnostic_signal_to_noise as gs384
from mide import webull_live


class _Provider:
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics


def test_stream_summary_surfaces_operational_truth_and_observational_30s_state():
    status, detail = gs384._stream_summary(
        {
            "webull_stream": {
                "authentication_status": "authenticated",
                "stream_connection_status": "connected",
                "subscribed_symbols": 55,
                "messages_received": 371,
                "tick_messages_received": 369,
                "stream_latency_ms": 62.49,
                "disconnect_count": 0,
                "subscription_failures": [],
                "thirty_second_bars_closed": 128,
                "thirty_second_symbols_ready": 14,
                "thirty_second_authority": "OBSERVATIONAL_ONLY",
            }
        }
    )

    assert status == "HEALTHY"
    assert "55 symbols" in detail
    assert "371 ticks" in detail
    assert "62 ms" in detail
    assert "0 disconnects" in detail
    assert "128 closed 30s bars" in detail
    assert "14 30s-ready symbols" in detail
    assert detail.endswith("OBSERVATIONAL_ONLY")


def test_stream_summary_does_not_call_disconnected_or_failed_subscription_healthy():
    status, detail = gs384._stream_summary(
        {
            "webull_stream": {
                "authentication_status": "authenticated",
                "stream_connection_status": "connected",
                "subscribed_symbols": 54,
                "subscription_failures": ["BADX: rejected"],
            }
        }
    )

    assert status == "CAUTION"
    assert "1 subscription errors" in detail


def test_pipeline_rows_enrich_stream_and_news_without_removing_existing_fields():
    provider = _Provider(
        {
            "webull_stream": {
                "authentication_status": "authenticated",
                "stream_connection_status": "connected",
                "subscribed_symbols": 55,
                "tick_messages_received": 5602,
                "stream_latency_ms": 62.36,
                "disconnect_count": 0,
                "subscription_failures": [],
                "thirty_second_bars_closed": 210,
                "thirty_second_symbols_ready": 20,
                "thirty_second_authority": "OBSERVATIONAL_ONLY",
            },
            "news_coverage": {
                "requests_made": 2,
                "articles_received": 68,
                "unique_symbols_discovered": 1,
                "provider_failures": 0,
            },
        }
    )
    rows = [
        {
            "Stage": "Streaming quotes",
            "Actual provider": "Webull OpenAPI SDK",
            "Endpoint / operation": "Official SDK market-data stream",
            "Code path": "existing stream path",
            "Alpaca used": "No",
        },
        {
            "Stage": "News",
            "Actual provider": "Financial Modeling Prep news",
            "Endpoint / operation": "Licensed catalyst feed: news/stock",
            "Code path": "existing news path",
            "Alpaca used": "No",
        },
        {
            "Stage": "Scanning / filtering",
            "Actual provider": "Walter local pipeline",
            "Endpoint / operation": "existing scan path",
            "Code path": "existing local path",
            "Alpaca used": "No",
        },
    ]

    enriched = gs384.enrich_pipeline_rows(provider, rows)

    assert enriched[0]["Actual provider"] == "Webull OpenAPI SDK • HEALTHY"
    assert "5602 ticks" in enriched[0]["Endpoint / operation"]
    assert "210 closed 30s bars" in enriched[0]["Endpoint / operation"]
    assert enriched[0]["Code path"] == "existing stream path"
    assert "68 articles" in enriched[1]["Endpoint / operation"]
    assert "0 provider failures" in enriched[1]["Endpoint / operation"]
    assert enriched[2] == rows[2]
    assert rows[0]["Actual provider"] == "Webull OpenAPI SDK"


def test_gs384_installs_after_existing_webull_pipeline_wrappers():
    assert getattr(
        webull_live.LiveWebullProvider.pipeline_sources,
        "_gs384_signal_to_noise",
        False,
    ) is True
