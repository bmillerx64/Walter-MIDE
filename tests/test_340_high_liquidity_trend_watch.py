import ast
from pathlib import Path

from mide import gs334_market_event_lane as lane
from mide.gs340_high_liquidity_trend_watch import high_liquidity_trend_rows


def _native(symbol, pct, rank, *, price=1.0, volume=60_000_000, sources=None):
    return {
        "symbol": symbol,
        "change_ratio": pct,
        "price": price,
        "volume": volume,
        "sources": sources or ["day_gainers"],
        "ranks": {"day_gainers": rank},
    }


def test_gs340_surfaces_gpro_like_high_liquidity_trend():
    rows = [_native("GPRO", 46.1, 4, price=0.88, volume=166_000_000)]

    events = high_liquidity_trend_rows(rows)

    assert [event["symbol"] for event in events] == ["GPRO"]
    assert events[0]["event_type"] == "high_liquidity_trend"
    assert events[0]["attention_only"] is True


def test_gs340_extends_existing_market_event_lane_without_replacing_extreme_movers():
    rows = [
        _native("WETO", 120.0, 1, price=4.0, volume=20_000_000),
        _native("CLGN", 95.0, 2, price=0.70, volume=120_000_000),
        _native("AEHL", 80.0, 3, price=4.50, volume=30_000_000),
        _native("GPRO", 46.1, 4, price=0.88, volume=166_000_000),
    ]

    events = lane.market_event_rows(rows)

    assert [event["symbol"] for event in events] == ["WETO", "CLGN", "AEHL", "GPRO"]
    assert all(event["attention_only"] is True for event in events)


def test_gs340_rejects_low_volume_high_price_low_gain_and_non_day_gainer_rows():
    rows = [
        _native("LOWV", 45.0, 2, volume=10_000_000),
        _native("PRICE", 45.0, 2, price=6.0, volume=100_000_000),
        _native("GAIN", 29.9, 2, volume=100_000_000),
        _native("RANK", 45.0, 11, volume=100_000_000),
        _native("RVOL", 45.0, 2, volume=100_000_000, sources=["relative_volume"]),
    ]

    assert high_liquidity_trend_rows(rows) == []


def test_gs340_does_not_duplicate_gs334_extreme_movers():
    rows = [_native("CLGN", 95.0, 1, price=0.70, volume=150_000_000)]

    events = lane.market_event_rows(rows)

    assert [event["symbol"] for event in events] == ["CLGN"]


def test_gs340_patch_is_installed():
    assert getattr(lane.market_event_rows, "_gs340_high_liquidity_trend_watch", False)


def test_gs340_does_not_import_trading_or_scanner_modules():
    source = Path("mide/gs340_high_liquidity_trend_watch.py").read_text()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden_fragments = ("alpaca", "execution", "orders", "scanner", "architecture")
    for module_name in imported:
        lowered = module_name.lower()
        assert not any(fragment in lowered for fragment in forbidden_fragments)
