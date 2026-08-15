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
        # Include one overlap to prove dedupe while preserving both source reasons.
        rows = [{"symbol": "G01", "volume": 9_999_999}]
        rows += [{"symbol": f"V{i:02d}", "volume": 9_000_000 - i}
                 for i in range(1, 25)]
        return rows


def _fresh_radar():
    """Reload the production module so GS262 is tested independently of prior test monkey-patches."""
    return importlib.reload(radar)


def test_gs262_scans_only_top20_day_gainers_and_top20_absolute_volume():
    native_radar = _fresh_radar()
    client = _Screener()
    report = native_radar.fetch_native_radar(client)

    assert report["discovery_contract"] == "WEBULL_TOP20_DAY_GAINERS_PLUS_TOP20_ABSOLUTE_VOLUME"
    assert report["maximum_pre_dedupe_symbols"] == 40
    assert report["pages_requested_per_feed"] == 1
    assert len(client.calls) == 2
    assert all(call[1]["page_index"] == 1 and call[1]["page_size"] == 20 for call in client.calls)
    assert client.calls[0][1]["rank_type"] == "DAY_1"
    assert client.calls[1][1]["rank_type"] == "VOLUME"
    assert report["unique_symbols"] == 39


def test_gs262_preserves_entry_reason_and_excludes_other_radar_feeds():
    native_radar = _fresh_radar()
    report = native_radar.fetch_native_radar(_Screener())
    by_symbol = {row["symbol"]: row for row in report["symbols"]}

    assert by_symbol["G01"]["sources"] == ["day_gainers", "absolute_volume"]
    assert by_symbol["G01"]["ranks"] == {"day_gainers": 1, "absolute_volume": 1}
    assert report["feeds"]["five_minute_movers"]["status"] == "NOT_SCANNED"
    assert report["feeds"]["relative_volume"]["status"] == "NOT_SCANNED"
    assert all(set(row["sources"]) <= {"day_gainers", "absolute_volume"}
               for row in report["symbols"])
