from mide.free_float import YahooFinanceFloatProvider
import mide.version  # activates live safety


def test_vivs_style_capital_structure_cannot_masquerade_as_low_float():
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
    assert resolved == 13_390_000
    assert resolved > 3_500_000


def test_tdic_style_structure_remains_inside_ceiling():
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
    assert resolved == 3_490_000
    assert resolved <= 3_500_000
