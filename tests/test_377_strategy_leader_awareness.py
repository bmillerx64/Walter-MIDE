import ast
from pathlib import Path

from mide import gs334_market_event_lane as lane
from mide.gs377_strategy_leader_awareness import (
    implied_previous_close,
    install,
    strategy_leader_rows,
)


def _native(symbol, pct, rank, *, price, volume=1_000_000, sources=None):
    return {
        "symbol": symbol,
        "change_ratio": pct,
        "price": price,
        "volume": volume,
        "sources": sources or ["day_gainers"],
        "ranks": {"day_gainers": rank},
    }


def test_ofal_style_sub5_current_leader_stays_in_operator_conversation():
    events = strategy_leader_rows([
        _native("OFAL", 18.83, 7, price=0.8065, volume=73_490_000),
    ])

    assert [event["symbol"] for event in events] == ["OFAL"]
    assert events[0]["attention_only"] is True
    assert events[0]["event_type"] == "strategy_leader"
    assert events[0]["strategy_price_reference"] == "current_price"


def test_pmi_style_breakout_above5_is_retained_when_move_started_below5():
    events = strategy_leader_rows([
        _native("PMI", 18.26, 8, price=5.31, volume=167_490),
    ])

    assert [event["symbol"] for event in events] == ["PMI"]
    assert events[0]["strategy_price_reference"] == "implied_previous_close"
    assert events[0]["implied_previous_close"] < 5.0
    assert round(implied_previous_close(5.31, 18.26), 2) == 4.49


def test_expensive_day_gainer_that_did_not_launch_from_sub5_is_not_added():
    events = strategy_leader_rows([
        _native("NIKI", 38.86, 1, price=9.04),
        _native("RDIB", 21.50, 5, price=16.70),
        _native("PDEX", 19.09, 6, price=73.54),
    ])

    assert events == []


def test_rule_requires_current_day_gainer_rank_and_meaningful_gain():
    rows = [
        _native("LOWGAIN", 14.99, 2, price=1.0),
        _native("RANK11", 30.0, 11, price=1.0),
        _native("RVOL", 30.0, 2, price=1.0, sources=["relative_volume"]),
    ]

    assert strategy_leader_rows(rows) == []


def test_gs377_extends_existing_lane_without_duplicate_trade_authority():
    install()
    events = lane.market_event_rows([
        _native("CLGN", 95.0, 1, price=0.70, volume=120_000_000),
        _native("OFAL", 18.83, 7, price=0.8065, volume=73_490_000),
        _native("PMI", 18.26, 8, price=5.31, volume=167_490),
    ])

    symbols = [event["symbol"] for event in events]
    assert symbols.count("CLGN") == 1
    assert "OFAL" in symbols
    assert "PMI" in symbols
    for event in events:
        assert event.get("attention_only") is True
        assert "qualified_for_entry" not in event
        assert "qualified_for_alert" not in event


def test_gs377_install_is_idempotent():
    install()
    first = lane.market_event_rows
    install()
    assert lane.market_event_rows is first
    assert getattr(first, "_gs377_strategy_leader_awareness", False)


def test_gs377_does_not_import_scanner_execution_or_architecture_modules():
    source = Path("mide/gs377_strategy_leader_awareness.py").read_text()
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    forbidden_fragments = ("scanner", "execution", "orders", "architecture", "alpaca")
    for module_name in imported:
        lowered = module_name.lower()
        assert not any(fragment in lowered for fragment in forbidden_fragments)
