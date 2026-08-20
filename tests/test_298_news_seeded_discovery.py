from datetime import datetime, timedelta, timezone

from mide.gs298_news_seeded_discovery import (
    MORNING_MOVER_SEED_REASON,
    NEWS_SEED_REASON,
    fetch_marketwide_stock_news,
    merge_news_seeds,
    morning_mover_attention_headline,
    select_material_news_seeds,
)
from mide.news_provider import NewsArticle

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)


def article(symbol, headline, *, source="Reuters", age_minutes=10):
    created = NOW - timedelta(minutes=age_minutes)
    return NewsArticle(
        id=f"{symbol}-{age_minutes}-{headline}",
        headline=headline,
        created_at=created,
        updated_at=None,
        symbols=[symbol],
        source=source,
        url="https://example.test/story",
        provider="Financial Modeling Prep",
    )


def test_material_reuters_and_benzinga_headlines_seed_symbols_and_preserve_sources():
    selected = select_material_news_seeds(
        [
            article("REUT", "REUT secures strategic contract", source="Reuters", age_minutes=8),
            article("BENZ", "BENZ receives new investment funding", source="Benzinga", age_minutes=12),
        ],
        now=NOW,
    )
    by_symbol = {item["symbol"]: item for item in selected}
    assert by_symbol["REUT"]["source"] == "Reuters"
    assert by_symbol["REUT"]["trusted_source"] is True
    assert by_symbol["BENZ"]["source"] == "Benzinga"
    assert by_symbol["BENZ"]["trusted_source"] is True
    assert by_symbol["REUT"]["catalyst_score"] >= 7
    assert by_symbol["BENZ"]["catalyst_score"] >= 7
    assert by_symbol["REUT"]["seed_type"] == "material_catalyst"
    assert by_symbol["BENZ"]["attention_only"] is False


def test_neutral_negative_stale_and_invalid_symbol_news_do_not_seed():
    selected = select_material_news_seeds(
        [
            article("NEUT", "NEUT comments on industry conditions"),
            article("DILU", "DILU announces registered direct offering"),
            article("OLD", "OLD wins strategic contract", age_minutes=361),
            article("BAD:US", "BAD secures contract"),
        ],
        now=NOW,
    )
    assert selected == []


def test_newest_material_article_wins_per_symbol_and_merge_does_not_duplicate_native_seed():
    selected = select_material_news_seeds(
        [
            article("NEW", "NEW wins contract", source="Reuters", age_minutes=20),
            article("NEW", "NEW receives strategic award", source="Benzinga", age_minutes=5),
            article("NATIVE", "NATIVE secures contract", source="Reuters", age_minutes=4),
        ],
        now=NOW,
    )
    seeds, reasons, added = merge_news_seeds(
        ["NATIVE"],
        {"NATIVE": ["Webull native market attention"]},
        selected,
    )
    assert seeds.count("NATIVE") == 1
    assert "NEW" in seeds
    assert [item["symbol"] for item in added] == ["NEW"]
    assert reasons["NEW"] == [f"{NEWS_SEED_REASON}: Benzinga"]


def test_fresh_premarket_roundup_can_seed_xos_without_catalyst_credit():
    selected = select_material_news_seeds(
        [
            article(
                "XOS",
                "12 Industrials Stocks Moving In Thursday's Pre-Market Session",
                source="Benzinga",
                age_minutes=18,
            )
        ],
        now=NOW,
    )
    assert len(selected) == 1
    item = selected[0]
    assert item["symbol"] == "XOS"
    assert item["seed_type"] == "morning_mover_attention"
    assert item["attention_only"] is True
    assert item["catalyst_score"] < 7
    seeds, reasons, added = merge_news_seeds([], {}, selected)
    assert seeds == ["XOS"]
    assert [row["symbol"] for row in added] == ["XOS"]
    assert reasons["XOS"] == [f"{MORNING_MOVER_SEED_REASON}: Benzinga"]


def test_fresh_healthcare_mover_roundup_can_seed_bivi_for_attention():
    selected = select_material_news_seeds(
        [
            article(
                "BIVI",
                "12 Health Care Stocks Moving In Thursday's Pre-Market Session",
                source="Benzinga",
                age_minutes=22,
            )
        ],
        now=NOW,
    )
    assert [item["symbol"] for item in selected] == ["BIVI"]
    assert selected[0]["seed_type"] == "morning_mover_attention"
    assert selected[0]["attention_only"] is True


def test_watchlist_and_trading_higher_headlines_are_attention_patterns():
    assert morning_mover_attention_headline(
        "Why Webull Shares Are Trading Higher By Around 14%; Here Are 20 Stocks Moving Premarket"
    )
    assert morning_mover_attention_headline(
        "Why These 3 Penny Stocks Are on Investors Radar, 8/20/26"
    )
    assert morning_mover_attention_headline("10 Stocks To Watch Before The Opening Bell")
    assert not morning_mover_attention_headline("Company comments on industry conditions")


def test_material_catalyst_beats_newer_roundup_for_same_symbol():
    selected = select_material_news_seeds(
        [
            article(
                "XOS",
                "12 Industrials Stocks Moving In Thursday's Pre-Market Session",
                source="Benzinga",
                age_minutes=3,
            ),
            article(
                "XOS",
                "XOS wins U.S. Air Force prototype contract",
                source="Reuters",
                age_minutes=20,
            ),
        ],
        now=NOW,
    )
    assert len(selected) == 1
    assert selected[0]["seed_type"] == "material_catalyst"
    assert "Air Force" in selected[0]["headline"]


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return [
            {
                "symbol": "WIRE",
                "title": "WIRE secures strategic contract",
                "publishedDate": "2026-08-19T19:55:00+00:00",
                "publisher": "Reuters",
                "url": "https://example.test/wire",
            }
        ]


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return FakeResponse()


def test_marketwide_fetch_uses_only_entitled_stock_news_and_no_symbol_filter():
    session = FakeSession()
    articles = fetch_marketwide_stock_news(
        "test-key",
        now=NOW,
        session=session,
    )
    assert len(session.calls) == 1
    url, params, timeout = session.calls[0]
    assert url.endswith("/news/stock")
    assert "press-releases" not in url
    assert "symbols" not in params
    assert timeout == 4
    assert articles[0].source == "Reuters"
    assert articles[0].symbols == ["WIRE"]


def test_news_seed_selection_is_bounded():
    rows = [
        article(f"S{i}", f"S{i} secures contract", age_minutes=i)
        for i in range(10)
    ]
    selected = select_material_news_seeds(rows, now=NOW, limit=3)
    assert len(selected) == 3
    assert [item["symbol"] for item in selected] == ["S0", "S1", "S2"]
