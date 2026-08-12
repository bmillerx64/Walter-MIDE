from types import SimpleNamespace

from mide.discovery import prefilter_snapshots
from mide.flight_recorder import prefilter_decision


SETTINGS = SimpleNamespace(
    min_price=0.05,
    max_price=5.0,
    min_pct_change=3.0,
    min_day_volume=100_000,
)


def snapshot(*, price=1.0, prev_close=1.0, volume=0):
    return {
        "latestTrade": {"p": price},
        "latestQuote": {"bp": price * 0.99, "ap": price * 1.01},
        "dailyBar": {"c": price, "v": volume, "h": price},
        "prevDailyBar": {"c": prev_close},
    }


def test_large_price_move_survives_even_when_snapshot_volume_is_temporarily_missing():
    result = prefilter_decision("MOVE", snapshot(price=1.20, prev_close=1.0, volume=0), SETTINGS)
    assert result["passed"] is True
    assert result["reason"] == "passed prefilter via price move"


def test_discovery_uses_installed_gain_or_participation_prefilter():
    selected = prefilter_snapshots(
        {"MOVE": snapshot(price=1.20, prev_close=1.0, volume=0)}, SETTINGS
    )
    assert [item["symbol"] for item in selected] == ["MOVE"]


def test_high_participation_survives_without_three_percent_gain():
    result = prefilter_decision("FLOW", snapshot(price=1.01, prev_close=1.0, volume=250_000), SETTINGS)
    assert result["passed"] is True
    assert result["reason"] == "passed prefilter via participation"


def test_quiet_symbol_still_fails_broad_prefilter():
    result = prefilter_decision("QUIET", snapshot(price=1.01, prev_close=1.0, volume=20_000), SETTINGS)
    assert result["passed"] is False
    assert result["failed_rule"] == "Percent change and average volume below thresholds"


def test_price_ceiling_is_unchanged():
    result = prefilter_decision("HIGH", snapshot(price=6.0, prev_close=4.0, volume=1_000_000), SETTINGS)
    assert result["passed"] is False
    assert result["failed_rule"] == "Price outside threshold"
