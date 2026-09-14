from mide.live_safety import _conservative_yahoo_share_structure


def test_outstanding_above_float_does_not_replace_float():
    payload = {"quoteSummary": {"result": [{"defaultKeyStatistics": {
        "floatShares": {"raw": 2_000_000},
        "sharesOutstanding": {"raw": 5_000_000},
    }}]}}
    assert _conservative_yahoo_share_structure(payload) == 2_000_000
