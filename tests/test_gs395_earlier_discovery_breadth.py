from mide.gs395_earlier_discovery_breadth import (
    SUPPLEMENTAL_UNIQUE_CAP,
    extend_report,
)


class _Screener:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def get_gainers_losers(self, **kwargs):
        self.calls.append(("gainers", dict(kwargs)))
        assert kwargs["rank_type"] == "MIN_5"
        assert kwargs["page_index"] == 2
        assert kwargs["page_size"] == 20
        if self.fail:
            raise RuntimeError("page 2 unavailable")
        return [
            {
                "symbol": f"M{index:02d}",
                "price": 1.0 + index / 100,
                "change_ratio": 5.0 + index,
                "volume": 100_000 + index,
            }
            for index in range(1, 13)
        ]

    def get_most_active(self, **kwargs):
        self.calls.append(("active", dict(kwargs)))
        assert kwargs["page_index"] == 2
        assert kwargs["page_size"] == 20
        if self.fail:
            raise RuntimeError("page 2 unavailable")
        if kwargs["rank_type"] == "RELATIVE_VOLUME_10D":
            return [
                {
                    "symbol": f"R{index:02d}",
                    "price": 1.2 + index / 100,
                    "change_ratio": 1.0 + index,
                    "volume": 80_000 + index,
                    "relative_volume_10d": 6.0 + index,
                }
                for index in range(1, 13)
            ]
        assert kwargs["rank_type"] == "VOLUME"
        return [
            {
                "symbol": f"A{index:02d}",
                "price": 2.0 + index / 100,
                "change_ratio": 3.0 + index,
                "volume": 2_000_000 + index,
            }
            for index in range(1, 13)
        ]


def _base_report():
    return {
        "symbols": [
            {
                "symbol": "BASE",
                "name": "Base",
                "price": 1.0,
                "change_ratio": 4.0,
                "volume": 900_000,
                "relative_volume_10d": 2.0,
                "sources": ["day_gainers"],
                "ranks": {"day_gainers": 1},
            }
        ],
        "unique_symbols": 1,
        "all_feeds_available": True,
        "discovery_contract": "BASE_CONTRACT",
        "maximum_pre_dedupe_symbols": 80,
    }


def test_gs395_adds_only_bounded_5m_and_absolute_volume_page2_symbols():
    screener = _Screener()
    result = extend_report(screener, _base_report())

    added = result["supplemental_breadth"]["symbols"]
    assert len(added) == SUPPLEMENTAL_UNIQUE_CAP == 20
    assert added[:12] == [f"M{index:02d}" for index in range(1, 13)]
    assert added[12:] == [f"A{index:02d}" for index in range(1, 9)]
    assert result["unique_symbols"] == 21
    assert result["maximum_pre_dedupe_symbols"] == 100
    assert result["all_feeds_available"] is True
    assert "PLUS_PAGE2_5MIN_ABSOLUTE_MAX20_UNIQUE" in result["discovery_contract"]

    # GS523 samples RVOL page 2 in a shadow-only lane. None of those rows may
    # enter the production discovery universe or consume the 20-symbol admission cap.
    shadow = result["supplemental_breadth"]["shadow_relative_volume_page2"]
    assert shadow["status"] == "PASS"
    assert shadow["symbols"] == [f"R{index:02d}" for index in range(1, 13)]
    assert shadow["admitted_to_discovery"] is False
    assert not any(symbol.startswith("R") for symbol in added)
    assert result["supplemental_breadth"]["relative_volume_role"].startswith("context/discovery")


def test_gs395_page2_failures_are_nonfatal_to_first_page_discovery():
    result = extend_report(_Screener(fail=True), _base_report())

    assert result["all_feeds_available"] is True
    assert result["unique_symbols"] == 1
    assert [row["symbol"] for row in result["symbols"]] == ["BASE"]
    assert result["supplemental_breadth"]["status"] == "CAUTION"
    assert result["supplemental_breadth"]["new_unique_symbols"] == 0
