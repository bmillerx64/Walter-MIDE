from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from mide.authorities import discovery_news, presentation_audio


UTC = timezone.utc
EASTERN = ZoneInfo("America/New_York")
NOW = datetime(2026, 9, 30, 12, 55, tzinfo=UTC)
CUTOFF = NOW - timedelta(hours=4)


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


def row(symbol, title, created, publisher="Reuters"):
    fmp_wall_clock = created.astimezone(EASTERN).replace(tzinfo=None)
    return {
        "symbol": symbol,
        "title": title,
        "publishedDate": fmp_wall_clock.strftime("%Y-%m-%d %H:%M:%S"),
        "publisher": publisher,
        "url": f"https://example.com/{symbol}/{int(created.timestamp())}",
    }


def test_gs610_uses_fmp_stock_latest_not_symbol_search_endpoint():
    session = FakeSession({
        0: [
            row(
                "CNTB",
                "Connect Biopharma reports positive Phase 2 COPD topline results",
                NOW - timedelta(minutes=70),
            )
        ]
    })

    articles, trace = discovery_news.fetch_fmp_marketwide_latest_for_brief(
        "secret",
        cutoff=CUTOFF,
        now=NOW,
        session=session,
    )

    assert [article.symbols for article in articles] == [["CNTB"]]
    assert session.calls
    assert session.calls[0][0].endswith("/stable/news/stock-latest")
    assert not session.calls[0][0].endswith("/stable/news/stock")
    assert trace["endpoint"] == "news/stock-latest"
    assert trace["articles_received"] == 1
    assert trace["source_counts"] == {"Reuters": 1}
    assert trace["priority_source_counts"] == {
        "Reuters": 1,
        "TipRanks": 0,
        "Benzinga": 0,
    }


def test_gs610_paginates_until_four_hour_cutoff_and_recovers_cntb():
    page0 = [
        row("ABCD", "ABCD signs strategic partnership agreement", NOW - timedelta(minutes=20)),
        row("EFGH", "EFGH receives government contract award", NOW - timedelta(minutes=50)),
    ]
    page1 = [
        row(
            "CNTB",
            "Connect Biopharma announces positive Phase 2 study results",
            NOW - timedelta(hours=2),
            publisher="TipRanks",
        ),
        row("IJKL", "IJKL announces patent license agreement", NOW - timedelta(hours=3)),
    ]
    page2 = [
        row("OLD", "OLD reports positive trial results", NOW - timedelta(hours=5)),
        row("OLDER", "OLDER receives contract", NOW - timedelta(hours=6)),
    ]
    session = FakeSession({0: page0, 1: page1, 2: page2})

    articles, trace = discovery_news.fetch_fmp_marketwide_latest_for_brief(
        "secret",
        cutoff=CUTOFF,
        now=NOW,
        session=session,
        page_size=2,
        max_pages=8,
    )

    symbols = [article.symbols[0] for article in articles]
    assert "CNTB" in symbols
    assert "OLD" not in symbols
    assert trace["pages_requested"] == 3
    assert trace["coverage_complete"] is True
    assert trace["page_cap_reached"] is False
    assert trace["priority_source_counts"]["Reuters"] == 3
    assert trace["priority_source_counts"]["TipRanks"] == 1


def test_gs610_reports_incomplete_coverage_when_page_cap_is_hit():
    session = FakeSession({
        0: [row("AAA", "AAA receives contract award", NOW - timedelta(minutes=10))],
        1: [row("BBB", "BBB reports positive clinical trial results", NOW - timedelta(minutes=20))],
    })

    articles, trace = discovery_news.fetch_fmp_marketwide_latest_for_brief(
        "secret",
        cutoff=CUTOFF,
        now=NOW,
        session=session,
        page_size=1,
        max_pages=2,
    )

    assert len(articles) == 2
    assert trace["pages_requested"] == 2
    assert trace["page_cap_reached"] is True
    assert trace["coverage_complete"] is False


def test_gs610_full_brief_classifies_recovered_cntb_as_clinical_catalyst(monkeypatch):
    recovered = [
        discovery_news.fetch_fmp_marketwide_latest_for_brief(
            "secret",
            cutoff=CUTOFF,
            now=NOW,
            session=FakeSession({
                0: [
                    row(
                        "CNTB",
                        "Connect Biopharma reports positive Phase 2 COPD topline results",
                        NOW - timedelta(minutes=70),
                    )
                ]
            }),
        )[0][0]
    ]

    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        benzinga_fetcher=lambda _cutoff, _now: [],
        fmp_fetcher=lambda _now: recovered,
    )

    assert report["cluster_count"] == 1
    cluster = report["clusters"][0]
    assert cluster["symbol"] == "CNTB"
    assert cluster["event_category"] == "REGULATORY_CLINICAL"
    assert cluster["news_class"] == "MATERIAL CATALYST"


def test_gs622_prefers_trusted_wire_as_cluster_representative_only():
    rows = [
        {
            "symbol": "WIRE",
            "category": "CONTRACT_ORDER",
            "news_class": "MATERIAL CATALYST",
            "created_at": NOW - timedelta(minutes=1),
            "headline": "WIRE contract analysis with stronger keyword score",
            "source": "Seeking Alpha",
            "provider": "Financial Modeling Prep",
            "catalyst_score": 30.0,
            "trusted_source": False,
        },
        {
            "symbol": "WIRE",
            "category": "CONTRACT_ORDER",
            "news_class": "MATERIAL CATALYST",
            "created_at": NOW - timedelta(minutes=2),
            "headline": "WIRE wins customer contract",
            "source": "Reuters",
            "provider": "Financial Modeling Prep",
            "catalyst_score": 12.0,
            "trusted_source": True,
        },
    ]

    cluster = discovery_news._cluster_brief_rows(rows, max_rows=1)[0]

    assert cluster["headline"] == "WIRE wins customer contract"
    assert cluster["confirmations"] == 2
    assert cluster["trusted_confirmation_count"] == 1
    assert cluster["trading_authority_changed"] is False


def test_gs622_provider_caption_exposes_priority_wire_coverage():
    report = {
        "providers": {
            "benzinga": {
                "transport_disposition": "UNAVAILABLE",
                "articles_received": 0,
            },
            "fmp": {
                "transport_disposition": "SUCCESS",
                "articles_received": 551,
                "pages_requested": 6,
                "coverage_complete": True,
                "priority_source_counts": {
                    "Reuters": 14,
                    "TipRanks": 9,
                    "Benzinga": 21,
                },
            },
        },
        "elapsed_ms": 1400,
    }

    caption = presentation_audio.catalyst_brief_provider_caption(report)

    assert "FMP: 551 articles / 6 pages / full requested window covered" in caption
    assert "wires Reuters 14, TipRanks 9, Benzinga 21" in caption
