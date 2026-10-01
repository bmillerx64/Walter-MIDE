from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from mide import gs620_live_news_stream as gs620
from mide import gs624_realtime_news_transport as gs624
from mide.authorities import presentation_audio


UTC = timezone.utc
NOW = datetime(2026, 10, 1, 13, 45, tzinfo=UTC)


class FakeSocket:
    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(json.loads(payload))


def reset_all():
    with gs620._LOCK:
        gs620._CACHE.clear()
        gs620._RUNTIME.clear()
        gs620._RUNTIME.update({
            "status": "cold",
            "last_started_at": None,
            "last_completed_at": None,
            "last_error_type": None,
            "articles_received": 0,
        })
        gs620._JOB = None
    gs624._reset_for_tests()


def test_gs624_alpaca_authentication_subscribes_marketwide_news():
    reset_all()
    ws = FakeSocket()

    gs624._handle_message(
        ws,
        json.dumps([{"T": "success", "msg": "connected"}]),
        received_at=NOW,
    )
    assert gs624.snapshot()["status"] == "connected"

    gs624._handle_message(
        ws,
        json.dumps([{"T": "success", "msg": "authenticated"}]),
        received_at=NOW,
    )

    snap = gs624.snapshot()
    assert snap["auth_status"] == "authenticated"
    assert ws.sent == [{"action": "subscribe", "news": ["*"]}]

    gs624._handle_message(
        ws,
        json.dumps([{"T": "subscription", "news": ["*"]}]),
        received_at=NOW,
    )
    snap = gs624.snapshot()
    assert snap["status"] == "streaming"
    assert snap["subscription_status"] == "marketwide_subscribed"


def test_gs624_push_news_enters_gs620_completed_cache_immediately():
    reset_all()
    ws = FakeSocket()
    created = NOW - timedelta(seconds=2.5)

    gs624._handle_message(
        ws,
        json.dumps([{
            "T": "n",
            "id": 123456,
            "headline": "FRESH wins material customer contract",
            "summary": "test",
            "author": "Benzinga Newsdesk",
            "created_at": created.isoformat(),
            "updated_at": created.isoformat(),
            "url": "https://example.test/fresh",
            "symbols": ["FRESH"],
            "source": "benzinga",
        }]),
        received_at=NOW,
    )

    rows = gs620.cached_articles(now=NOW)
    assert len(rows) == 1
    assert rows[0].symbols == ["FRESH"]
    assert rows[0].source == "benzinga"
    assert rows[0].provider == "Alpaca realtime news"

    stream = gs624.snapshot()
    assert stream["messages_received"] == 1
    assert stream["articles_ingested"] == 1
    assert stream["newest_article_at"] == created.isoformat()
    assert stream["newest_article_age_at_receipt_seconds"] == 2.5

    rows, cache = gs620.cache_snapshot(now=NOW)
    assert len(rows) == 1
    assert cache["newest_age_seconds"] == 2.5
    assert cache["last_push_received_at"] == NOW.isoformat()
    assert cache["push_articles_received"] == 1
    assert cache["realtime_transport"]["status"] == "streaming"
    assert cache["scan_blocked"] is False
    assert cache["trading_authority_changed"] is False


def test_gs624_safe_failure_categories_distinguish_connection_and_entitlement():
    reset_all()
    ws = FakeSocket()

    gs624._handle_message(
        ws,
        json.dumps([{"T": "error", "code": 406, "msg": "connection limit exceeded"}]),
        received_at=NOW,
    )
    snap = gs624.snapshot()
    assert snap["last_error_category"] == "connection_limit"
    assert snap["last_error_code"] == "406"

    reset_all()
    gs624._handle_message(
        ws,
        json.dumps([{"T": "error", "code": 403, "msg": "subscription not permitted"}]),
        received_at=NOW,
    )
    snap = gs624.snapshot()
    assert snap["last_error_category"] == "subscription_or_entitlement"
    assert snap["auth_status"] == "rejected"


def test_gs624_credentials_are_reused_but_never_exposed_in_snapshot():
    class AlpacaClient:
        headers = {
            "APCA-API-KEY-ID": "key-value",
            "APCA-API-SECRET-KEY": "secret-value",
        }

    class AlpacaProvider:
        client = AlpacaClient()

    class LiveWebull:
        _universe_client = AlpacaProvider()

    assert gs624._credentials_from_client(LiveWebull()) == (
        "key-value",
        "secret-value",
    )
    serialized = json.dumps(gs624.snapshot())
    assert "key-value" not in serialized
    assert "secret-value" not in serialized
    assert "APCA-API-SECRET-KEY" not in serialized


def test_gs624_caption_exposes_push_transport_truth():
    report = {
        "providers": {
            "alpaca_live": {
                "transport_disposition": "SUCCESS",
                "articles_received": 21,
                "newest_article_at": "2026-10-01T13:44:58+00:00",
                "newest_age_seconds": 2.0,
                "last_completed_at": "2026-10-01T13:44:20+00:00",
                "realtime_transport": {
                    "status": "streaming",
                    "subscription_status": "marketwide_subscribed",
                    "articles_ingested": 17,
                    "last_error_category": None,
                },
            },
            "benzinga": {
                "transport_disposition": "UNAVAILABLE",
                "articles_received": 0,
            },
            "fmp": {
                "transport_disposition": "SUCCESS",
                "articles_received": 500,
                "newest_article_at": "2026-10-01T13:35:00+00:00",
                "newest_age_seconds": 600.0,
                "pages_requested": 5,
                "coverage_complete": True,
                "priority_source_counts": {
                    "Reuters": 8,
                    "TipRanks": 0,
                    "Benzinga": 12,
                },
                "tipranks_zero_reason": (
                    "complete FMP window contained no source label matching TipRanks"
                ),
            },
        },
        "elapsed_ms": 1400,
    }

    caption = presentation_audio.catalyst_brief_provider_caption(report)

    assert "Live cache: 21 articles" in caption
    assert "stream streaming" in caption
    assert "marketwide_subscribed" in caption
    assert "push 17" in caption
    assert "REST poll completed 2026-10-01T13:44:20+00:00" in caption


def test_gs624_install_order_and_authority_boundary_are_explicit():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    source = Path("mide/gs624_realtime_news_transport.py").read_text(encoding="utf-8")
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "install_gs620()" in startup
    assert "install_gs624()" in startup
    assert startup.index("install_gs620()") < startup.index("install_gs624()")
    assert "websocket-client==1.9.2" in requirements
    assert 'news": ["*"]' in source

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)
