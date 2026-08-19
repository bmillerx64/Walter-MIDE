from datetime import datetime, timedelta, timezone

from mide.architecture import ArchitecturePolicy, Decision, WalterArchitectureV1
from mide.webull_native_radar import fetch_native_radar


class Store:
    def __init__(self):
        self.results = None

    def persist(self, results):
        self.results = results


def _passing(records):
    return {row["symbol"]: Decision(True, "test", "passed") for row in records}


def _architecture(scans):
    now = datetime(2026, 8, 19, 12, tzinfo=timezone.utc)
    store = Store()
    architecture = WalterArchitectureV1(
        policy=ArchitecturePolicy(.05, 5, 3_500_000),
        discover=lambda: scans.pop(0), catalyst=_passing, participation=_passing,
        expansion=_passing, rank=lambda rows: rows, store=store, publish=lambda rows: None,
        clock=lambda: now + timedelta(seconds=architecture.candidate_ledger.scan_number),
    )
    return architecture, store


def test_new_candidate_is_visible_on_its_first_refresh_and_keeps_market_state():
    architecture, _ = _architecture([[{
        "symbol": "NEW", "price": 1.25, "change_ratio": 4.2, "volume": 50_000,
        "sources": ["relative_volume"], "free_float": 1_000_000,
    }]])
    record = architecture.run()[0]
    assert record["entered_active_candidate_universe"] is True
    assert record["discovery_first_seen_at"] == record["discovery_last_seen_at"]
    assert record["discovery_history"][0] == {
        "event": "first_seen", "timestamp": record["discovery_first_seen_at"], "scan": 1,
        "source_path": ["relative_volume"], "price": 1.25,
        "market_state": {"change_ratio": 4.2, "volume": 50_000},
        "entered_active_candidate_universe": True, "rejection_reason": None,
    }


def test_refresh_disappearance_is_audited_and_rediscovery_preserves_first_seen():
    row = {"symbol": "BACK", "price": 1, "free_float": 1_000_000, "source": "day_gainers"}
    architecture, _ = _architecture([[row], [], [row]])
    first = architecture.run()[0]["discovery_first_seen_at"]
    absent = architecture.run()[0]
    assert absent["entered_active_candidate_universe"] is False
    assert absent["discovery_history"][-1]["rejection_reason"] == "Not present in current live universe"
    returned = architecture.run()[0]
    assert returned["discovery_first_seen_at"] == first
    assert [event["event"] for event in returned["discovery_history"]] == [
        "first_seen", "absent_from_refresh", "rediscovered"
    ]


class Screener:
    def get_gainers_losers(self, **kwargs):
        return [{"symbol": "GAIN", "change_ratio": 5, "price": 2}]

    def get_most_active(self, **kwargs):
        if kwargs["rank_type"] == "RELATIVE_VOLUME_10D":
            return [{"symbol": "FLAT", "change_ratio": 1.5, "price": 3, "volume": 10_000}]
        return [{"symbol": "ACTIVE", "change_ratio": 3, "price": 4}]


def test_discovery_rejection_retains_exact_reason_without_changing_filter():
    report = fetch_native_radar(Screener())
    assert "FLAT" not in {row["symbol"] for row in report["symbols"]}
    rejection = report["rejected_symbols"][0]
    assert rejection["symbol"] == "FLAT"
    assert rejection["entered_active_candidate_universe"] is False
    assert rejection["discovery_rejection_reason"] == (
        "relative_volume change_ratio 1.5 below 2.0% minimum"
    )


def test_discovery_audit_does_not_change_downstream_membership_or_rank():
    rows = [
        {"symbol": "ONE", "price": 1, "free_float": 1_000_000},
        {"symbol": "TWO", "price": 6, "free_float": 1_000_000},
    ]
    architecture, _ = _architecture([rows])
    results = architecture.run()
    assert [(row["symbol"], row["terminal_stage"], row.get("mission_rank")) for row in results] == [
        ("ONE", "Mission Ranking and Publication", 1), ("TWO", "Price Gate", None)
    ]
