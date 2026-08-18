import importlib

import mide  # noqa: F401
from mide import webull_native_radar as radar


class _Screener:
    def __init__(self):
        self.calls = []

    def get_gainers_losers(self, **kwargs):
        self.calls.append(("gainers", kwargs))
        return [{"symbol": f"G{i:02d}", "change_ratio": 50 - i, "volume": 1000 + i}
                for i in range(1, 26)]

    def get_most_active(self, **kwargs):
        self.calls.append(("active", kwargs))
        # Include one overlap (G01) to prove dedupe while preserving both source reasons.
        rows = [{"symbol": "G01", "volume": 9_999_999}]
        rows += [{"symbol": f"V{i:02d}", "volume": 9_000_000 - i}
                 for i in range(1, 25)]
        return rows


def _fresh_radar():
    """Reload the production module so discovery tests are independent of prior monkey-patches."""
    return importlib.reload(radar)


def test_discovery_feeds_include_day_gainers_absolute_volume_and_relative_volume():
    native_radar = _fresh_radar()
    client = _Screener()
    report = native_radar.fetch_native_radar(client)

    assert report["discovery_contract"] == (
        "WEBULL_TOP20_DAY_GAINERS_PLUS_TOP20_ABSOLUTE_VOLUME_PLUS_TOP20_RELATIVE_VOLUME"
    )
    # Three feeds are now active (day_gainers, absolute_volume, relative_volume).
    assert report["pages_requested_per_feed"] == 1
    # One get_gainers_losers call (day_gainers) and two get_most_active calls
    # (absolute_volume + relative_volume).
    assert len(client.calls) == 3
    assert all(call[1]["page_index"] == 1 and call[1]["page_size"] == 20 for call in client.calls)
    assert client.calls[0][1]["rank_type"] == "DAY_1"
    assert client.calls[1][1]["rank_type"] == "VOLUME"
    assert client.calls[2][1]["rank_type"] == "RELATIVE_VOLUME_10D"


def test_discovery_preserves_source_labels_and_excludes_five_minute_movers():
    native_radar = _fresh_radar()
    report = native_radar.fetch_native_radar(_Screener())
    by_symbol = {row["symbol"]: row for row in report["symbols"]}

    # G01 appears in day_gainers, absolute_volume, and relative_volume.
    assert set(by_symbol["G01"]["sources"]) == {"day_gainers", "absolute_volume", "relative_volume"}
    # five_minute_movers is still NOT_SCANNED.
    assert report["feeds"]["five_minute_movers"]["status"] == "NOT_SCANNED"
    # relative_volume is now PASS (it is a discovery feed).
    assert report["feeds"]["relative_volume"]["status"] == "PASS"
    # No symbol should have five_minute_movers as a source.
    assert all("five_minute_movers" not in row["sources"] for row in report["symbols"])
