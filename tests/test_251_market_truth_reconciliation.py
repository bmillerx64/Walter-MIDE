from mide.market_truth_reconciliation import (
    market_truth_reconciliation,
    market_truth_row,
    market_truth_summary,
)


SCAN = "2026-08-14T16:26:55+00:00"


def flight(symbol="WALT", qualified=True, displayed=True):
    return {
        "funnel": {"Qualified": int(qualified), "Displayed": int(displayed)},
        "symbols": [{
            "symbol": symbol,
            "events": [
                {"stage": "qualified_for_ranking", "passed": qualified},
                {"stage": "actionable display", "passed": displayed},
            ],
        }],
    }


def record(**overrides):
    row = {
        "symbol": "WALT",
        "price": 10.0,
        "snapshot_price": 10.0,
        "last_bar_close": 10.02,
        "previous_close": 9.5,
        "pct_change": 5.2632,
        "volume": 250000,
        "vwap_value": 9.8,
        "supertrend_bullish": True,
        "source_bar_timestamp": "2026-08-14T16:26:30+00:00",
        "candidate_status": "Entry Ready",
        "entry_ready": True,
        "rank": 1,
    }
    row.update(overrides)
    return row


def test_reconciled_market_truth_row_is_explicit_and_complete():
    row = market_truth_row(record(), scan_timestamp=SCAN, flight_row=flight()["symbols"][0])
    assert row["symbol"] == "WALT"
    assert row["source_bar_age_seconds"] == 25.0
    assert row["price_divergence_pct"] == 0.2
    assert row["calculated_pct_change"] == 5.2632
    assert row["flight_qualified_for_ranking"] is True
    assert row["flight_actionable_display"] is True
    assert row["issues"] == []
    assert row["reconciled"] is True


def test_price_and_percent_change_mismatches_are_exposed_not_hidden():
    row = market_truth_row(
        record(last_bar_close=11.0, pct_change=20.0),
        scan_timestamp=SCAN,
        flight_row=flight()["symbols"][0],
    )
    assert "snapshot_bar_price_mismatch" in row["issues"]
    assert "pct_change_mismatch" in row["issues"]
    assert row["reconciled"] is False


def test_ranked_candidate_vs_flight_recorder_contradiction_is_detected():
    row = market_truth_row(
        record(),
        scan_timestamp=SCAN,
        flight_row=flight(qualified=False, displayed=False)["symbols"][0],
    )
    assert "candidate_flight_qualification_mismatch" in row["issues"]
    assert "candidate_flight_display_mismatch" in row["issues"]


def test_scan_report_detects_observed_published_vs_flight_funnel_contradiction():
    snapshot = flight(qualified=False, displayed=False)
    snapshot["funnel"] = {"Qualified": 0, "Displayed": 0}
    report = market_truth_reconciliation([record()], scan_timestamp=SCAN, flight_snapshot=snapshot)
    assert report["status"] == "CONTRADICTIONS"
    assert report["records_audited"] == 1
    assert report["reconciled_records"] == 0
    assert report["contradictory_records"] == 1
    assert "published_vs_flight_qualified_count_mismatch" in report["funnel_issues"]
    assert "published_vs_flight_displayed_count_mismatch" in report["funnel_issues"]
    assert report["issue_counts"]["candidate_flight_qualification_mismatch"] == 1


def test_empty_scan_is_unmeasured_not_falsely_reconciled():
    report = market_truth_reconciliation([], scan_timestamp=SCAN, flight_snapshot={})
    assert report["status"] == "UNMEASURED"
    assert report["reconciled_pct"] is None
    assert market_truth_summary(report) == "Market truth: UNMEASURED · 0 records · N/A reconciled · 0 contradictory"


def test_diagnostics_do_not_mutate_candidate_input():
    candidate = record()
    before = dict(candidate)
    market_truth_reconciliation([candidate], scan_timestamp=SCAN, flight_snapshot=flight())
    assert candidate == before
