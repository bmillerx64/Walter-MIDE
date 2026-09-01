from mide.gs349_operator_first_layout import developing_now_markup


def test_developing_summary_uses_trigger_authoritative_vwap_and_participation(monkeypatch):
    from mide import ui

    record = {
        "symbol": "ITP",
        "price": 0.1608,
        "pct_change": -10.0,
        # Convenience fields intentionally disagree with the trigger snapshots.
        "vwap_distance_pct": -0.8,
        "participation_score": 19,
        "expansion_score": 57,
        "expansion_quality": 57,
        "supertrend_bullish": True,
        "strengthening_vwap_gate": {"distance_pct": -2.6},
        "participation_surge_diagnostics": {"participation_score": 34},
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
    assert "VWAP -0.8%" not in markup
    assert "Participation 19" not in markup


def test_developing_summary_falls_back_when_diagnostics_absent(monkeypatch):
    from mide import ui

    record = {
        "symbol": "FALL",
        "price": 1.0,
        "pct_change": 5.0,
        "vwap_distance_pct": 0.4,
        "participation_surge_score": 62,
        "expansion_quality": 58,
        "supertrend_bullish": True,
    }
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING (1)", records, True)],
    )

    markup = developing_now_markup([record])
    assert "VWAP +0.4%" in markup
    assert "Participation 62" in markup
    assert "Expansion 58" in markup
