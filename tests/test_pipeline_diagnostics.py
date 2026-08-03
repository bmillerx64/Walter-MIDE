from mide.architecture import Decision
from mide.pipeline_diagnostics import (
    diagnostics_table,
    pre_expansion_candidate_diagnostics,
    stage_diagnostic,
)


def test_stage_diagnostic_accounts_for_rejections_missing_values_and_top_ten():
    inputs = [
        {"symbol": "AAA", "price": 1.0, "volume": None},
        {"symbol": "BBB", "price": None, "volume": None},
        {"symbol": "CCC", "price": 3.0, "volume": 100},
    ]
    diagnostic = stage_diagnostic(
        "Prefilter", inputs, inputs[-1:],
        rejection_reasons=["low volume", "low volume"],
        fields=("price", "volume"),
    )

    assert diagnostic["input_count"] == 3
    assert diagnostic["output_count"] == 1
    assert diagnostic["rejection_count"] == 2
    assert diagnostic["top_10_rejection_reasons"] == [
        {"reason": "low volume", "count": 2}
    ]
    assert diagnostic["missing_fields_encountered"] == [
        {"field": "volume", "count": 2},
        {"field": "price", "count": 1},
    ]
    assert diagnostic["missing_values_pct"] == 66.67


def test_diagnostics_table_makes_each_count_drop_visible():
    stage = stage_diagnostic(
        "Snapshot retrieval",
        [{"symbol": "AAA", "price": None}], [],
        rejection_reasons=["Snapshot unavailable"], fields=("price",),
    )

    assert diagnostics_table([stage]) == [{
        "Stage": "Snapshot retrieval",
        "Input": 1,
        "Output": 0,
        "Rejected": 1,
        "Top rejection reasons": "Snapshot unavailable (1)",
        "Missing fields": "price (1)",
        "Symbols missing values": "100.00%",
    }]


def test_pre_expansion_diagnostics_keeps_rejections_and_ranks_top_twenty():
    records = [
        {
            "symbol": f"S{index:02}", "scanner_v2_score": index,
            "price": 1.25, "volume": 1_000_000 + index,
            "float_shares": 2_000_000, "rvol_proxy": 2.5,
            "spread_pct": 0.4, "participation_score": 70,
        }
        for index in range(25)
    ]
    decisions = {
        record["symbol"]: Decision(
            record["symbol"] != "S24", "Expansion", "Confluence",
            {"confluence_score": 45 if record["symbol"] == "S24" else 82},
        )
        for record in records
    }

    rows = pre_expansion_candidate_diagnostics(records, decisions)

    assert len(rows) == 20
    assert rows[0] == {
        "Rank before Expansion": 1,
        "Symbol": "S24",
        "Price": 1.25,
        "Volume": 1_000_024.0,
        "Float": 2_000_000.0,
        "RVOL": 2.5,
        "Spread %": 0.4,
        "Participation score": 70.0,
        "Expansion score": 45.0,
        "Mission score": 24.0,
        "Expansion result": "REJECTED",
        "Rejected because": "expansion_score = 45; required = 65",
    }
    assert rows[-1]["Symbol"] == "S05"
