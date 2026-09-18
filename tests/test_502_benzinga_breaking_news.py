from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs502_benzinga_breaking_news as gs502


UTC = timezone.utc
NOW = datetime(2026, 9, 18, 14, 40, tzinfo=UTC)


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, headers, timeout):
        self.calls.append((url, dict(params), dict(headers), timeout))
        return FakeResponse(self.payload)


def benzinga_row(symbol="SDST"):
    return {
        "id": 12345,
        "created": "Fri, 18 Sep 2026 10:38:00 -0400",
        "updated": "Fri, 18 Sep 2026 10:38:05 -0400",
        "title": f"{symbol} secures $120 million strategic agreement",
        "body": (
            f"<p>{symbol} announced a strategic agreement worth $120 million "
            "with a commercial partner. The company expects expansion.</p>"
        ),
        "url": "https://example.test/story",
        "stocks": [{"name": symbol, "exchange": "NASDAQ"}],
    }


def test_normalize_benzinga_article_preserves_story_for_existing_interpreter():
    article = gs502.normalize_benzinga_article(benzinga_row())

    assert article is not None
    assert article.source == "Benzinga"
    assert article.provider == "Benzinga Newsfeed"
    assert article.symbols == ["SDST"]
    assert article.created_at == datetime(2026, 9, 18, 14, 38, tzinfo=UTC)
    assert "120 million" in getattr(article, "_walter_story_text")
    context = getattr(article, "_walter_story_context")
    assert "CONTRACT_ORDER" in context["categories"]
    assert context["material_attention"] is True


def test_direct_fetch_uses_updated_since_and_header_auth_not_query_token():
    session = FakeSession([benzinga_row()])
    since = NOW - timedelta(minutes=3)

    articles = gs502.fetch_benzinga_delta(
        "TOP_SECRET",
        since=since,
        now=NOW,
        session=session,
    )

    assert [article.symbols for article in articles] == [["SDST"]]
    url, params, headers, timeout = session.calls[0]
    assert url == gs502.ENDPOINT
    assert params["updatedSince"] == int(since.timestamp())
    assert params["pageSize"] == 100
    assert params["displayOutput"] == "full"
    assert "token" not in params
    assert headers["Authorization"] == "token TOP_SECRET"
    assert timeout == gs502.HTTP_TIMEOUT_SECONDS


def test_missing_token_makes_zero_requests_and_does_not_change_discovery(monkeypatch):
    class Client:
        provider_name = "Webull OpenAPI"
        diagnostics = {}

    monkeypatch.setattr(gs502, "_configured_benzinga_token", lambda: "")
    seeds, reasons = gs502.merge_breaking_news_discovery(
        Client(),
        ["NATIVE"],
        {"NATIVE": ["Webull native"]},
        now=NOW,
    )

    assert seeds == ["NATIVE"]
    assert reasons["NATIVE"] == ["Webull native"]
    assert Client.diagnostics["benzinga_breaking_news"]["request_made"] is False


def test_breaking_material_article_adds_identity_but_no_gate_authority(monkeypatch):
    from mide import gs298_news_seeded_discovery as gs298

    class Client:
        provider_name = "Webull OpenAPI"
        diagnostics = {}

    article = gs502.normalize_benzinga_article(benzinga_row("SDST"))
    monkeypatch.setattr(gs502, "_configured_benzinga_token", lambda: "configured")
    monkeypatch.setattr(
        gs502,
        "poll_breaking_news",
        lambda **kwargs: (
            [article],
            {
                "authority": gs502.AUTHORITY,
                "configured": True,
                "request_made": True,
                "articles_received": 1,
                "cached_articles": 1,
                "transport_disposition": "SUCCESS_WITH_ARTICLES",
                "trading_authority_changed": False,
            },
        ),
    )

    seeds, reasons = gs502.merge_breaking_news_discovery(
        Client(),
        [],
        {},
        now=NOW,
    )

    assert seeds == ["SDST"]
    assert any("Benzinga" in reason for reason in reasons["SDST"])
    trace = Client.diagnostics["benzinga_breaking_news"]
    assert trace["symbols_added"] == ["SDST"]
    assert trace["trading_authority_changed"] is False

    selected = gs298.select_material_news_seeds([article], now=NOW)
    assert selected[0]["seed_type"] == "material_catalyst"


def test_cached_article_survives_empty_next_delta(monkeypatch):
    gs502._ARTICLE_CACHE.clear()
    gs502._LAST_SUCCESSFUL_POLL = None
    article = gs502.normalize_benzinga_article(benzinga_row("KEEP"))

    calls = iter([[article], []])
    monkeypatch.setattr(
        gs502,
        "fetch_benzinga_delta",
        lambda *args, **kwargs: next(calls),
    )

    first, first_trace = gs502.poll_breaking_news(
        token="configured",
        now=NOW,
    )
    second, second_trace = gs502.poll_breaking_news(
        token="configured",
        now=NOW + timedelta(minutes=1),
    )

    assert [item.symbols for item in first] == [["KEEP"]]
    assert [item.symbols for item in second] == [["KEEP"]]
    assert first_trace["articles_received"] == 1
    assert second_trace["articles_received"] == 0
    assert second_trace["cached_articles"] == 1


def test_recorder_trace_persists_bounded_transport_and_selection():
    captured = {}

    def baseline(_recorder, scan, records):
        captured["scan"] = scan
        return scan

    gs502._LATEST_TRACE = {
        "authority": gs502.AUTHORITY,
        "configured": True,
        "request_made": True,
        "articles_received": 3,
        "selected_symbols": ["SDST"],
        "symbols_added": ["SDST"],
        "trading_authority_changed": False,
    }
    wrapped = gs502._recorder_wrapper(baseline)
    wrapped(object(), {"scan_id": "one"}, [])

    assert captured["scan"]["benzinga_breaking_news_trace"]["selected_symbols"] == ["SDST"]
    assert captured["scan"]["benzinga_breaking_news_trace"]["trading_authority_changed"] is False


def test_startup_installs_gs502_after_story_intelligence_before_transport_observers():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]

    assert "gs502_benzinga_breaking_news" in source
    assert body.index("install_gs480()") < body.index("install_gs502()") < body.index("install_gs481()")


def test_scope_lock_keeps_breaking_news_out_of_trading_authority():
    source = Path("mide/gs502_benzinga_breaking_news.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert "updatedSince" in source
    assert "Authorization" in source
