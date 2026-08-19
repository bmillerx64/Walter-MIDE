from mide.news_provider import FMPNewsProvider


def test_fmp_entitlement_contract_is_stock_news_only():
    assert FMPNewsProvider.ENTITLED_ENDPOINTS == ("news/stock",)
    assert all("press-releases" not in endpoint for endpoint in FMPNewsProvider.ENTITLED_ENDPOINTS)
