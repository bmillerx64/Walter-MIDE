from types import SimpleNamespace

from mide import ui
from mide.gs334_market_event_lane import (
    completed_scan_market_events,
    market_event_markup,
    market_event_rows,
    visible_market_events,
)
from mide.webull_live import LiveWebullProvider


def _native(symbol, pct, rank, *, sources=None):
    return {
        "symbol": symbol,
        "change_ratio": pct,
        "price": 1.23,
        "volume": 10_000_000,
        "sources": sources or ["day_gainers"],
        "ranks": {"day_gainers": rank},
    }


def test_gs334_surfaces_extreme_day_gainers_without_trade_promotion():
    rows = [
        _native("WETO", 123.95, 1),
        _native("CLGN", 99.11, 2),
        _native("AEHL", 79.10, 3),
        _native("RDHL", 62.63, 4),
        _native("RVOL", 250.0, 1, sources=["relative_volume"]),
    ]

    events = market_event_rows(rows)

    assert [event["symbol"] for event in events] == ["WETO", "CLGN", "AEHL"]
    assert all(event["attention_only"] is True for event in events)
    assert events[0]["pct_change"] == 123.95
    assert events[0]["rank"] == 1


def test_gs334_suppresses_symbols_already_in_current_trade_results():
    events = market_event_rows([
        _native("WETO", 123.95, 1),
        _native("CLGN", 99.11, 2),
    ])

    visible = visible_market_events(events, ["WETO"])

    assert [event["symbol"] for event in visible] == ["CLGN"]


def test_gs334_markup_is_explicitly_attention_only():
    events = market_event_rows([_native("CLGN", 99.11, 2)])

    markup = market_event_markup(events)

    assert "LIVE MARKET EVENTS" in markup
    assert "ATTENTION ONLY" in markup
    assert "CLGN" in markup
    assert "+99.1%" in markup
    assert "normal entry gates still apply" in markup


def test_gs335_reads_events_from_authoritative_completed_scan():
    expected = market_event_rows([
        _native("WETO", 122.73, 1),
        _native("CLGN", 92.18, 2),
        _native("AEHL", 75.14, 3),
    ])
    scan = SimpleNamespace(diagnostics={
        "market_event_lane": {
            "source": "Webull native DAY_GAINERS",
            "attention_only": True,
            "events": expected,
        }
    })

    events = completed_scan_market_events({"completed_scan": scan})

    assert [event["symbol"] for event in events] == ["WETO", "CLGN", "AEHL"]
    assert events == expected
    assert events is not expected


def test_gs335_uses_scan_context_compatibility_path():
    expected = market_event_rows([_native("WETO", 122.73, 1)])
    scan = SimpleNamespace(diagnostics={"market_event_lane": {"events": expected}})
    state = {"scan_context": SimpleNamespace(completed_scan=scan)}

    assert completed_scan_market_events(state) == expected


def test_gs334_wrappers_are_installed_without_erasing_prior_contracts():
    assert getattr(ui.mission_control_header_markup, "_gs334_market_event_lane", False)
    assert getattr(ui.mission_control_header_markup, "_gs335_persistent_market_events", False)
    assert getattr(ui.mission_control_header_markup, "_gs332_action_first", False)
    assert getattr(ui.walter_mission_control, "_gs334_market_event_symbols", False)
    assert getattr(ui.walter_mission_control, "_gs310_unified_state", False)
    assert getattr(LiveWebullProvider.assets, "_gs334_market_event_capture", False)
    assert getattr(LiveWebullProvider.assets, "_gs263_discovery_gate", False)
