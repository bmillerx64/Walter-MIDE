from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs298_news_seeded_discovery as gs298
from mide.authorities import discovery_news
from mide.news import classify_headline, trusted_catalyst_source
from mide.news_provider import FMPNewsProvider


UTC = timezone.utc
NOW = datetime(2026, 9, 30, 14, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return FakeResponse(self.pages.get(params["page"], []))


def row(symbol, title, stamp, publisher="TipRanks", text=""):
    return {
        "symbol": symbol,
        "title": title,
        "publishedDate": stamp.isoformat(),
        "publisher": publisher,
        "text": text,
        "url": f"https://example.test/{symbol}/{int(stamp.timestamp())}",
    }


def test_gs618_bootstraps_two_latest_pages_then_warm_polls_page_zero_only():
    discovery_news._FMP_LATEST_DISCOVERY_CACHE.clear()
    discovery_news._FMP_LATEST_DISCOVERY_TRACE.clear()
    session = FakeSession({
        0: [row(
            "FNGR",
            "FingerMotion To Acquire Newbit For $2.3 Mln In Cash",
            NOW - timedelta(minutes=8),
            publisher="NASDAQ",
        )],
        1: [row(
            "GCDT",
            "Green Circle Tenders HK$67 Million HVAC Decarbonization Projects in Hong Kong",
            NOW - timedelta(hours=2),
        )],
    })

    first = discovery_news.fetch_fmp_latest_discovery_news(
        "secret", now=NOW, session=session, limit=1
    )

    assert [call[0] for call in session.calls] == [
        f"{FMPNewsProvider.BASE_URL}/news/stock-latest",
        f"{FMPNewsProvider.BASE_URL}/news/stock-latest",
    ]
    assert [call[1]["page"] for call in session.calls] == [0, 1]
    assert {article.symbols[0] for article in first} == {"FNGR", "GCDT"}
    assert discovery_news._FMP_LATEST_DISCOVERY_TRACE["bootstrap"] is True

    session.calls.clear()
    session.pages = {
        0: [row(
            "NEWX",
            "NEWX signs strategic partnership agreement",
            NOW + timedelta(minutes=1),
            publisher="Reuters",
        )]
    }
    second = discovery_news.fetch_fmp_latest_discovery_news(
        "secret", now=NOW + timedelta(minutes=1), session=session, limit=1
    )

    assert len(session.calls) == 1
    assert session.calls[0][1]["page"] == 0
    assert {article.symbols[0] for article in second} == {"FNGR", "GCDT", "NEWX"}
    assert discovery_news._FMP_LATEST_DISCOVERY_TRACE["bootstrap"] is False
    assert discovery_news._FMP_LATEST_DISCOVERY_TRACE["trading_authority_changed"] is False


def test_gs618_fngr_acquisition_from_latest_feed_is_material_identity_seed():
    article = FMPNewsProvider._normalize(
        row(
            "FNGR",
            "FingerMotion To Acquire Newbit For $2.3 Mln In Cash",
            NOW - timedelta(minutes=8),
            publisher="NASDAQ",
        ),
        endpoint="news/stock-latest",
    )
    selected = gs298.select_material_news_seeds([article], now=NOW)

    assert selected[0]["symbol"] == "FNGR"
    assert selected[0]["seed_type"] == "material_catalyst"
    assert selected[0]["catalyst_score"] >= 7
    assert trusted_catalyst_source("NASDAQ") is True


def test_gs618_gcdt_tender_is_attention_only_not_awarded_contract():
    headline = "Green Circle Tenders HK$67 Million HVAC Decarbonization Projects in Hong Kong"
    detail = discovery_news.story_intelligence(headline)
    score, _flags = classify_headline(headline)

    assert "TENDER_PROPOSAL" in detail["categories"]
    assert detail["attention_only_categories"] == ["TENDER_PROPOSAL"]
    assert "CONTRACT_ORDER" not in detail["categories"]
    assert detail["material_attention"] is True
    assert score == 0
    assert detail["catalyst_score_changed"] is False
    assert detail["trading_authority_changed"] is False


def test_gs618_tender_story_can_seed_identity_without_catalyst_credit():
    discovery_news._install_article_transport()
    discovery_news._install_marketwide_selection()
    article = FMPNewsProvider._normalize(
        row(
            "GCDT",
            "Green Circle submits two proposals for Chiller replacement engineering",
            NOW - timedelta(minutes=20),
            publisher="TipRanks",
            text="The proposals concern HVAC replacement projects in Hong Kong.",
        ),
        endpoint="news/stock-latest",
    )
    selected = gs298.select_material_news_seeds([article], now=NOW, limit=20)
    item = next(row for row in selected if row["symbol"] == "GCDT")

    assert item["seed_type"] == discovery_news.STORY_SEED_TYPE
    assert item["attention_only"] is True
    assert item["catalyst_score"] == 0.0
    assert "TENDER_PROPOSAL" in item["story_context"]["categories"]


def test_gs618_startup_order_and_scope_lock():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")
    body = startup.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs480()") < body.index("install_gs618()") < body.index("install_gs502()")

    source = Path("mide/gs618_fmp_latest_discovery.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
