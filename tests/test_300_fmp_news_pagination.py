from datetime import datetime, timedelta, timezone

import pytest

from mide.gs300_fmp_news_pagination import (
    NEWS_FEED_MAX_PAGES,
    fetch_marketwide_stock_news_paginated,
)

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)


class Response:
    def __init__(self, rows, *, error=False):
        self.rows = rows
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise RuntimeError("boom")

    def json(self):
        return self.rows


class Session:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        page = params["page"]
        value = self.pages.get(page, [])
        if isinstance(value, Exception):
            raise value
        return Response(value)


def row(symbol, minutes_old, source="Reuters", title=None):
    return {
        "symbol": symbol,
        "title": title or f"{symbol} announces strategic agreement",
        "publishedDate": (NOW - timedelta(minutes=minutes_old)).isoformat(),
        "publisher": source,
        "url": f"https://example.test/{symbol}/{minutes_old}",
    }


def full_page(prefix, start_age):
    return [row(f"{prefix}{index}", start_age + index) for index in range(100)]


def test_fetch_reaches_deeper_pages_when_page_zero_is_full():
    session = Session({
        0: full_page("A", 1),
        1: [row("DEEP", 140, source="Benzinga")],
    })
    articles = fetch_marketwide_stock_news_paginated(
        "secret", now=NOW, session=session
    )
    assert "DEEP" in {symbol for article in articles for symbol in article.symbols}
    assert [call[1]["page"] for call in session.calls] == [0, 1]
    assert all(call[0].endswith("/news/stock") for call in session.calls)
    assert all("symbols" not in call[1] for call in session.calls)


def test_reuters_and_benzinga_source_labels_are_preserved_on_deeper_pages():
    session = Session({
        0: full_page("A", 1),
        1: [row("RTR", 90, "Reuters"), row("BENZ", 91, "Benzinga")],
    })
    articles = fetch_marketwide_stock_news_paginated(
        "secret", now=NOW, session=session
    )
    by_symbol = {
        article.symbols[0]: article.source
        for article in articles
        if article.symbols and article.symbols[0] in {"RTR", "BENZ"}
    }
    assert by_symbol == {"RTR": "Reuters", "BENZ": "Benzinga"}


def test_short_page_stops_pagination_early():
    session = Session({0: [row("ONE", 10)]})
    fetch_marketwide_stock_news_paginated("secret", now=NOW, session=session)
    assert [call[1]["page"] for call in session.calls] == [0]


def test_pagination_is_bounded_even_when_every_page_is_full():
    session = Session({
        0: full_page("A", 1),
        1: full_page("B", 101),
        2: full_page("C", 201),
        3: [row("TOO_DEEP", 250)],
    })
    fetch_marketwide_stock_news_paginated("secret", now=NOW, session=session)
    assert [call[1]["page"] for call in session.calls] == list(range(NEWS_FEED_MAX_PAGES))
    assert all(call[1]["limit"] == 100 for call in session.calls)


def test_deeper_page_failure_preserves_successful_page_zero_news():
    session = Session({
        0: full_page("A", 1),
        1: RuntimeError("page one unavailable"),
    })
    articles = fetch_marketwide_stock_news_paginated(
        "secret", now=NOW, session=session
    )
    assert len(articles) == 100
    assert fetch_marketwide_stock_news_paginated.last_page_failures == 1
    assert fetch_marketwide_stock_news_paginated.last_pages_requested == 2


def test_page_zero_failure_preserves_gs298_fail_open_contract():
    session = Session({0: RuntimeError("page zero unavailable")})
    with pytest.raises(RuntimeError):
        fetch_marketwide_stock_news_paginated("secret", now=NOW, session=session)


def test_stale_rows_from_deeper_pages_are_not_returned():
    session = Session({
        0: full_page("A", 1),
        1: [row("FRESH", 300), row("STALE", 361)],
    })
    articles = fetch_marketwide_stock_news_paginated(
        "secret", now=NOW, session=session
    )
    symbols = {symbol for article in articles for symbol in article.symbols}
    assert "FRESH" in symbols
    assert "STALE" not in symbols


def test_duplicate_articles_across_pages_are_deduplicated():
    duplicate = row("DUP", 30)
    page0 = [duplicate, *full_page("A", 1)[:99]]
    page1 = [duplicate]
    session = Session({0: page0, 1: page1})
    articles = fetch_marketwide_stock_news_paginated(
        "secret", now=NOW, session=session
    )
    dup_articles = [article for article in articles if "DUP" in article.symbols]
    assert len(dup_articles) == 1
