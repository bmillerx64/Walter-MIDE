from mide.live_safety import _conservative_yahoo_share_structure


def test_float_boundary_uses_floatshares_not_outstanding():
    payload = {
        "quoteSummary": {
            "result": [{
                "defaultKeyStatistics": {
                    "floatShares": {"raw": 3_400_000},
                    "sharesOutstanding": {"raw": 3_500_000},
                }
            }]
        }
    }
    assert _conservative_yahoo_share_structure(payload) == 3_400_000
