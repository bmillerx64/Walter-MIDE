from mide.live_safety import _conservative_yahoo_share_structure


def test_missing_share_structure_remains_unresolved():
    assert _conservative_yahoo_share_structure({"quoteSummary": {"result": []}}) is None
