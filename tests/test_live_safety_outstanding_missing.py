from mide.live_safety import _conservative_yahoo_share_structure


def test_float_is_preserved_when_outstanding_is_unavailable():
    payload = {
        "quoteSummary": {
            "result": [{"defaultKeyStatistics": {"floatShares": {"raw": 2_280_000}}}]
        }
    }
    assert _conservative_yahoo_share_structure(payload) == 2_280_000
