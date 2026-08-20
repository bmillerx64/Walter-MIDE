from mide.gs312_scan_stage_timing import timing_snapshot, timing_summary_line


def test_timing_snapshot_identifies_slowest_stage_without_retiming():
    source = [
        {"stage": "Universe Construction", "elapsed_ms": 1200, "input_count": 0, "output_count": 35},
        {"stage": "Market Data Retrieval", "elapsed_ms": 900, "input_count": 30, "output_count": 30},
        {"stage": "Participation Assessment", "elapsed_ms": 16700, "input_count": 15, "output_count": 15},
        {"stage": "Total Scan", "elapsed_ms": 20100, "input_count": 35, "output_count": 5},
    ]
    before = [dict(row) for row in source]

    snapshot = timing_snapshot(source)

    assert snapshot["measured"] is True
    assert snapshot["total_seconds"] == 20.1
    assert snapshot["slowest_stage"] == "Participation Assessment"
    assert snapshot["slowest_seconds"] == 16.7
    assert snapshot["slowest_share_pct"] == 83.1
    assert source == before


def test_timing_snapshot_uses_sum_when_total_row_is_absent():
    snapshot = timing_snapshot([
        {"stage": "Universe Construction", "elapsed_ms": 1000},
        {"stage": "Participation Assessment", "elapsed_ms": 3000},
    ])

    assert snapshot["total_seconds"] == 4.0
    assert snapshot["slowest_stage"] == "Participation Assessment"
    assert snapshot["slowest_share_pct"] == 75.0


def test_timing_summary_line_is_compact_and_descriptive():
    line = timing_summary_line(
        {
            "measured": True,
            "total_seconds": 20.1,
            "slowest_stage": "Participation Assessment",
            "slowest_seconds": 16.7,
            "slowest_share_pct": 83.1,
        }
    )

    assert line == (
        "Last scan: 20.1s · Slowest: Participation Assessment "
        "16.7s (83% of total)"
    )


def test_missing_timing_is_silent():
    assert timing_snapshot(None)["measured"] is False
    assert timing_summary_line({"measured": False}) == ""
