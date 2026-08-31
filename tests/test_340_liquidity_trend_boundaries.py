from mide.gs340_high_liquidity_trend_watch import high_liquidity_trend_rows


def _row(*, pct=30.0, price=5.0, volume=50_000_000, rank=10):
    return {
        "symbol": "EDGE",
        "change_ratio": pct,
        "price": price,
        "volume": volume,
        "sources": ["day_gainers"],
        "ranks": {"day_gainers": rank},
    }


def test_gs340_accepts_exact_boundary_values():
    events = high_liquidity_trend_rows([_row()])
    assert [event["symbol"] for event in events] == ["EDGE"]


def test_gs340_remains_attention_only_at_boundaries():
    event = high_liquidity_trend_rows([_row()])[0]
    assert event["attention_only"] is True
    assert "qualified" not in event
    assert "entry_ready" not in event
