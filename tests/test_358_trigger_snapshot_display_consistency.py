from mide.gs349_operator_first_layout import developing_now_markup


def test_developing_summary_uses_same_stored_trigger_snapshot_as_entry_locks(monkeypatch):
    from mide import ui

    record = {
        "symbol": "GYGY",
        "price": 1.38,
        "pct_change": 16.0,
        "supertrend_bullish": True,
        # Later/current diagnostic maps intentionally drift from the trigger
        # snapshot, matching the live GS357 observation.
        "strengthening_vwap_gate": {"distance_pct": -6.6},
        "participation_surge_diagnostics": {"participation_score": 62},
        "expansion_quality": 33,
        "trigger_diagnostics": {
            "passed": False,
            "checks": [
                {
                    "condition": "supertrend_flip",
                    "passed": False,
                    "failed_reason": "ST Flip not detected (Requires flip within 10 minutes)",
                },
                {
                    "condition": "vwap",
                    "passed": False,
                    "failed_reason": "Price 3.1% below VWAP (Entry floor = -0.75%)",
                },
                {
                    "condition": "participation",
                    "passed": True,
                    "passed_reason": "Participation Surge 71/100 (Pass ≥60)",
                },
                {
                    "condition": "expansion_beginning",
                    "passed": False,
                    "failed_reason": "Expansion Quality 33/100 (Below trigger threshold of 55)",
                },
            ],
        },
    }

    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING (1)", records, True)],
    )

    markup = developing_now_markup([record])
    assert "VWAP -3.1%" in markup
    assert "Participation 71" in markup
    assert "Expansion 33" in markup
    assert "VWAP -6.6%" not in markup
    assert "Participation 62" not in markup


def test_developing_summary_preserves_gs354_fallback_without_stored_trigger(monkeypatch):
    from mide import ui

    record = {
        "symbol": "FALL",
        "price": 1.0,
        "pct_change": 5.0,
        "supertrend_bullish": True,
        "strengthening_vwap_gate": {"distance_pct": -2.6},
        "participation_surge_diagnostics": {"participation_score": 34},
        "expansion_quality": 57,
    }

    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING (1)", records, True)],
    )

    markup = developing_now_markup([record])
    assert "VWAP -2.6%" in markup
    assert "Participation 34" in markup
    assert "Expansion 57" in markup
