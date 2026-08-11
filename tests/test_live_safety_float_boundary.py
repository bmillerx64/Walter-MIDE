from mide.live_safety import _conservative_yahoo_share_structure


def test_exact_3_5m_capital_structure_remains_eligible_for_float_ceiling():
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
    assert _conservative_yahoo_share_structure(payload) == 3_500_000
