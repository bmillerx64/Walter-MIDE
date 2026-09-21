from mide import ui
from mide import gs348_st_vwap_operator_priority as gs348
from mide.gs349_operator_first_layout import developing_now_markup, developing_records


def _record(symbol: str, *, state: str = "DEVELOPING", volume: int = 600_000):
    return {
        "symbol": symbol,
        "price": 1.25,
        "pct_change": 14.0,
        "candidate_status": state,
        "opportunity_state": state,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.7,
        "supertrend_bullish": True,
        "participation_score": 34,
        "expansion_score": 52,
        "volume": volume,
    }


def test_installed_render_contract_is_operator_first():
    assert getattr(ui.render_walter_mission_control, "_gs349_operator_first_layout", False)


def test_developing_summary_uses_existing_display_sections(monkeypatch):
    dev = _record("DEV")
    ready = _record("READY", state="LOOK NOW")
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [
            ("LOOK NOW (1)", [ready], True),
            ("DEVELOPING (1)", [dev], True),
        ],
    )
    assert developing_records([ready, dev]) == [dev]


def test_developing_markup_puts_current_patterns_ahead_of_history(monkeypatch):
    dev = _record("OLOX")
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING (1)", [dev], True)],
    )
    monkeypatch.setattr(gs348, "active_cross", lambda symbol: symbol == "OLOX")

    markup = developing_now_markup([dev])

    assert "DEVELOPING NOW" in markup
    assert "OLOX" in markup
    assert "ST/VWAP CROSS · WATCH NOW" in markup
    assert "Historical additions/removals remain in Live Opportunity Feed below" in markup


def test_developing_summary_is_empty_when_no_developing_rows(monkeypatch):
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("LOOK NOW (1)", [_record("HOT", state="LOOK NOW")], True)],
    )
    assert developing_now_markup([]) == ""


def test_gs513_developing_summary_uses_same_walter_priority_as_detail(monkeypatch):
    scni = {
        **_record("SCNI"),
        "current_momentum": 52.2,
        "historical_strength": 41.1,
        "participation_surge_score": 0.0,
        "relative_strength_score": 8.1,
        "alignment_score": 1.0,
    }
    sdst = {
        **_record("SDST"),
        "current_momentum": 46.8,
        "historical_strength": 42.9,
        "participation_surge_score": 0.0,
        "relative_strength_score": 2.88,
        "alignment_score": 0.0,
    }
    gtec = {
        **_record("GTEC"),
        "current_momentum": 42.7,
        "historical_strength": 25.5,
        "participation_surge_score": 0.0,
        "relative_strength_score": 2.52,
        "alignment_score": 0.0,
    }
    monkeypatch.setattr(
        ui,
        "scanner_v2_display_sections",
        lambda records: [("DEVELOPING (3)", [sdst, gtec, scni], True)],
    )

    ordered = developing_records([sdst, gtec, scni])

    assert [record["symbol"] for record in ordered] == ["SCNI", "SDST", "GTEC"]
