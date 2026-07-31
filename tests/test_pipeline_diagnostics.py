from mide.pipeline_diagnostics import diagnostics_table, stage_diagnostic


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
