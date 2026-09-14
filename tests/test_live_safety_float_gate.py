from mide.free_float import YahooFinanceFloatProvider
import mide.version  # activates live safety


def test_outstanding_cannot_masquerade_as_free_float():
    payload = {
        "quoteSummary": {
            "result": [{
                "defaultKeyStatistics": {
                    "floatShares": {"raw": 1_000_000},
                    "sharesOutstanding": {"raw": 13_390_000},
                }
            }]
        }
    }
    resolved = YahooFinanceFloatProvider.parse(payload)
    assert resolved == 1_000_000


def test_float_inside_ceiling_stays_inside_even_with_larger_outstanding():
    payload = {
        "quoteSummary": {
            "result": [{
                "defaultKeyStatistics": {
                    "floatShares": {"raw": 2_660_000},
                    "sharesOutstanding": {"raw": 3_490_000},
                }
            }]
        }
    }
    resolved = YahooFinanceFloatProvider.parse(payload)
    assert resolved == 2_660_000
    assert resolved <= 3_500_000
