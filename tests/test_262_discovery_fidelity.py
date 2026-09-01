import importlib

import mide  # noqa: F401
from mide import webull_native_radar as radar


class _Screener:
    def __init__(self):
        self.calls = []

    def get_gainers_losers(self, **kwargs):
        self.calls.append(("gainers", kwargs))
        prefix = "G" if kwargs["rank_type"] == "DAY_1" else "M"
        return [{"symbol": f"{prefix}{i:02d}", "change_ratio": 50 - i,
                 "volume": 1000 + i}
                for i in range(1, 26)]

    def get_most_active(self, **kwargs):
        self.calls.append(("active", kwargs))
        # Include one overlap (G01) to prove dedupe while preserving source reasons.
        rows = [{"symbol": "G01", "volume": 9_999_999}]
        rows += [{"symbol": f"V{i:02d}", "volume": 9_000_000 - i}
                 for i in range(1, 25)]
        return rows


def _fresh_radar():
    """Reload the production module so discovery tests are independent of prior monkey-patches."""
    return importlib.reload(radar)


def test_discovery_feeds_include_all_four_native_attention_lists():
    native_radar = _fresh_radar()
    client = _Screener()
    report = native_radar.fetch_native_radar(client)

    assert report["discovery_contract"] == (
        "WEBULL_TOP20_DAY_GAINERS_PLUS_TOP20_FIVE_MINUTE_MOVERS_PLUS_TOP20_ABSOLUTE_VOLUME_PLUS_TOP20_RELATIVE_VOLUME"
    )
    assert report["maximum_pre_dedupe_symbols"] == 80
    assert report["pages_requested_per_feed"] == 1
    # Two get_gainers_losers calls (day + five-minute) and two get_most_active calls.
    assert len(client.calls) == 4
    assert all(call[1]["page_index"] == 1 and call[1]["page_size"] == 20 for call in client.calls)
    assert client.calls[0][1]["rank_type"] == "DAY_1"
    assert client.calls[1][1]["rank_type"] == "MIN_5"
    assert client.calls[2][1]["rank_type"] == "VOLUME"
    assert client.calls[3][1]["rank_type"] == "RELATIVE_VOLUME_10D"


def test_discovery_preserves_source_labels_and_includes_five_minute_movers():
    native_radar = _fresh_radar()
    report = native_radar.fetch_native_radar(_Screener())
    by_symbol = {row["symbol"]: row for row in report["symbols"]}

    # G01 appears in day_gainers, absolute_volume, and relative_volume.
    assert set(by_symbol["G01"]["sources"]) == {"day_gainers", "absolute_volume", "relative_volume"}
    # M01 is unique to the re-enabled fast-mover lane.
    assert by_symbol["M01"]["sources"] == ["five_minute_movers"]
    assert report["feeds"]["five_minute_movers"]["status"] == "PASS"
    assert report["feeds"]["relative_volume"]["status"] == "PASS"
