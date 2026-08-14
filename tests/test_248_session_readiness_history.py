from datetime import datetime, timedelta, timezone

from mide.completed_scan import CompletedScan, publish_scan_result, store_completed_scan
from mide.evidence_readiness_history import READINESS_HISTORY_KEY, readiness_history


BASE_TIME = datetime(2026, 8, 14, 15, 0, tzinfo=timezone.utc)


def scan_at(completed_at, symbol="WALT"):
    return CompletedScan(
        provider="WEBULL",
        records=[{
            "symbol": symbol,
            "price": 10.0,
            "volume": 100_000,
            "vwap_value": 9.8,
            "supertrend_bullish": True,
            "source_bar_timestamp": completed_at.isoformat(),
            "timeframes": {"1m": {}},
            "candidate_status": "Watching",
            "conviction_score": 72,
        }],
        diagnostics={"scan_completed": True},
        warnings=[],
        symbols_sampled=1,
        prefilter_count=1,
        completed_at=completed_at,
        source_label="Live WEBULL",
    )


def test_each_published_completed_scan_appends_its_stored_readiness_snapshot():
    state = {}
    first = scan_at(BASE_TIME, "AAA")
    second = scan_at(BASE_TIME + timedelta(minutes=1), "BBB")

    publish_scan_result(state, first)
    publish_scan_result(state, second)

    history = readiness_history(state)
    assert len(history) == 2
    assert history[0]["completed_at"] == BASE_TIME.isoformat()
    assert history[1]["completed_at"] == (BASE_TIME + timedelta(minutes=1)).isoformat()
    assert history[0]["provider"] == history[1]["provider"] == "WEBULL"
    assert history[0]["readiness_snapshot"] == first.diagnostics["evidence_readiness"]
    assert history[1]["readiness_snapshot"] == second.diagnostics["evidence_readiness"]


def test_history_is_detached_from_later_diagnostics_mutation():
    state = {}
    scan = scan_at(BASE_TIME)
    store_completed_scan(state, scan)
    expected = readiness_history(state)[0]["readiness_snapshot"]

    scan.diagnostics["evidence_readiness"]["status"] = "MUTATED"
    scan.diagnostics["evidence_readiness"]["reasons"].append("later change")

    assert readiness_history(state)[0]["readiness_snapshot"] == expected
    assert readiness_history(state)[0]["readiness_snapshot"]["status"] != "MUTATED"


def test_republishing_same_completed_scan_does_not_duplicate_history():
    state = {}
    scan = scan_at(BASE_TIME)

    store_completed_scan(state, scan)
    store_completed_scan(state, scan)

    assert len(state[READINESS_HISTORY_KEY]) == 1


def test_failed_or_zero_symbol_scan_does_not_append_history():
    state = {}
    good = scan_at(BASE_TIME)
    publish_scan_result(state, good)

    failed = CompletedScan(
        provider="WEBULL",
        records=[],
        diagnostics={"scan_completed": False},
        warnings=["transport interrupted"],
        symbols_sampled=0,
        prefilter_count=0,
        completed_at=BASE_TIME + timedelta(minutes=1),
        source_label="failed",
    )
    assert publish_scan_result(state, failed) is good
    assert len(readiness_history(state)) == 1


def test_readiness_history_returns_a_detached_copy():
    state = {}
    publish_scan_result(state, scan_at(BASE_TIME))

    observed = readiness_history(state)
    observed[0]["readiness_snapshot"]["status"] = "CHANGED"

    assert readiness_history(state)[0]["readiness_snapshot"]["status"] != "CHANGED"
