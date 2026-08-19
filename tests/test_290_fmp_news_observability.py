from mide.gs290_fmp_news_observability import fmp_news_audit_rows, fmp_news_audit_summary


def _metrics():
    return {
        "active_provider": "Financial Modeling Prep news",
        "requested_symbols": ["BTCT", "SKK"],
        "query_since": "2026-08-19T18:00:00+00:00",
        "effective_provider_since": "2026-08-19T18:00:00+00:00",
        "provider_endpoints": ["news/stock"],
        "requests_made": 1,
        "articles_received": 2,
        "symbols_with_articles": ["BTCT"],
        "symbols_without_articles": ["SKK"],
        "newest_articles_by_symbol": {
            "SKK": {"articles_returned": 0, "material_article_count": 0},
            "BTCT": {
                "articles_returned": 2,
                "newest_article_age_minutes": 18.0,
                "newest_headline": "BTC Digital announces strategic agreement",
                "newest_source": "Example Wire",
                "newest_provider": "Financial Modeling Prep",
                "newest_catalyst_score": 6,
                "newest_catalyst_flags": ["strategic"],
                "material_article_count": 1,
                "selected_material_headline": "BTC Digital wins major contract",
                "selected_material_score": 12,
                "selected_material_flags": ["contract"],
            },
        },
    }


def test_audit_rows_expose_what_walter_saw_without_reclassification():
    rows = fmp_news_audit_rows(_metrics())
    assert [row["symbol"] for row in rows] == ["BTCT", "SKK"]
    assert rows[0]["articles_returned"] == 2
    assert rows[0]["newest_age_minutes"] == 18.0
    assert rows[0]["newest_headline"] == "BTC Digital announces strategic agreement"
    assert rows[0]["source"] == "Example Wire"
    assert rows[0]["selected_material_headline"] == "BTC Digital wins major contract"
    assert rows[0]["disposition"] == "MATERIAL CATALYST SELECTED"
    assert rows[1]["disposition"] == "NO ARTICLES RETURNED"


def test_summary_exposes_endpoint_and_entire_requested_symbol_set():
    summary = fmp_news_audit_summary(_metrics())
    assert summary["provider_endpoints"] == ["news/stock"]
    assert summary["requested_symbols"] == ["BTCT", "SKK"]
    assert summary["symbols_audited"] == 2
    assert summary["symbols_with_material"] == 1
    assert summary["symbols_with_selected_material"] == 1
    assert summary["diagnostic_only"] is True
