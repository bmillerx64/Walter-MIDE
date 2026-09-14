from mide.free_float import YahooFinanceFloatProvider
import mide.live_safety  # noqa: F401 - activates the live safety parser binding
from mide.live_safety import _conservative_yahoo_share_structure


def _payload(float_shares=None, shares_outstanding=None):
    statistics = {}
    if float_shares is not None:
        statistics["floatShares"] = {"raw": float_shares}
    if shares_outstanding is not None:
        statistics["sharesOutstanding"] = {"raw": shares_outstanding}
    return {"quoteSummary": {"result": [{"defaultKeyStatistics": statistics}]}}


def test_mwc_regression_42m_float_is_not_replaced_by_59m_outstanding():
    """MWC 2026-09-14: Webull showed 42.06M float / 59.42M outstanding."""
    payload = _payload(
        float_shares=42_060_000,
        shares_outstanding=59_419_414,
    )

    resolved = YahooFinanceFloatProvider.parse(payload)

    assert resolved == 42_060_000
    assert resolved <= 50_000_000
    assert resolved != 59_419_414


def test_shares_outstanding_alone_never_becomes_free_float():
    payload = _payload(shares_outstanding=59_419_414)

    assert _conservative_yahoo_share_structure(payload) is None
    assert YahooFinanceFloatProvider.parse(payload) is None


def test_larger_true_float_still_fails_50m_ceiling():
    payload = _payload(
        float_shares=59_419_414,
        shares_outstanding=80_000_000,
    )

    resolved = YahooFinanceFloatProvider.parse(payload)

    assert resolved == 59_419_414
    assert resolved > 50_000_000
