from mide.live_safety import _conservative_yahoo_share_structure


def test_outstanding_above_float_is_not_ignored():
    payload = {"quoteSummary": {"result": [{"defaultKeyStatistics": {
        "floatShares": {"raw": 2_000_000},
        "sharesOutstanding": {"raw": 5_000_000},
    }}]}}
    assert _conservative_yahoo_share_structure(payload) == 5_000_000
