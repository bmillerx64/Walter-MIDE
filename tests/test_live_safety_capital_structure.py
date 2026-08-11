from mide.live_safety import _conservative_yahoo_share_structure


def test_larger_reported_float_still_wins_over_outstanding():
    payload = {
        "quoteSummary": {
            "result": [{
                "defaultKeyStatistics": {
                    "floatShares": {"raw": 4_200_000},
                    "sharesOutstanding": {"raw": 4_000_000},
                }
            }]
        }
    }
    assert _conservative_yahoo_share_structure(payload) == 4_200_000
