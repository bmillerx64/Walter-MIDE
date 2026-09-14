from mide.live_safety import _conservative_yahoo_share_structure


def test_small_float_remains_small_even_when_outstanding_is_larger():
    payload = {"quoteSummary": {"result": [{"defaultKeyStatistics": {
        "floatShares": {"raw": 1_190_000},
        "sharesOutstanding": {"raw": 2_930_000},
    }}]}}
    assert _conservative_yahoo_share_structure(payload) == 1_190_000
