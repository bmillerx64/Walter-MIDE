from mide import gs421_multitimeframe_convergence_recorder as gs421
from mide import gs422_convergence_recorder_performance as gs422
from mide.flight_recorder_gold import make_paths_replayable


def test_only_current_signal_records_pay_for_maturation_study():
    ordinary = {
        "symbol": "QUIET",
        "status": "PASS",
        "qualified_for_watch": False,
        "qualified_for_entry": False,
    }
    assert gs422.should_record_maturation(ordinary) is False
    assert gs422.should_record_maturation({**ordinary, "qualified_for_watch": True}) is True
    assert gs422.should_record_maturation(
        {**ordinary, "operator_investigation_tripwire": True}
    ) is True
    assert gs422.should_record_maturation({**ordinary, "st_vwap_cross_recent": True}) is True
    assert gs422.should_record_maturation({**ordinary, "status": "Strengthening"}) is True


def test_install_short_circuits_expensive_gs421_build_for_ordinary_record(monkeypatch):
    calls = []

    def expensive(record, raw_rows, client):
        calls.append(record["symbol"])
        return {"authority": "OBSERVATIONAL_ONLY", "available": True}

    monkeypatch.setattr(gs421, "build_maturation_evidence", expensive)
    gs422.install()

    quiet = gs421.build_maturation_evidence(
        {
            "symbol": "QUIET",
            "status": "PASS",
            "qualified_for_watch": False,
            "qualified_for_entry": False,
        },
        [{}],
        object(),
    )
    assert quiet["skipped"] is True
    assert quiet["available"] is False
    assert calls == []

    signal = gs421.build_maturation_evidence(
        {
            "symbol": "TNON",
            "status": "PASS",
            "qualified_for_watch": True,
            "qualified_for_entry": False,
        },
        [{}],
        object(),
    )
    assert signal["available"] is True
    assert calls == ["TNON"]


def test_flight_recorder_projection_persists_maturation_package():
    package = {
        "authority": "OBSERVATIONAL_ONLY",
        "available": True,
        "observed_cascade": ["1m", "3m", "5m"],
        "highest_observed_maturation": "5m",
    }
    paths = [{"symbol": "TNON"}]
    records = [
        {
            "symbol": "TNON",
            "price": 4.39,
            "participation_gate": {"passed": True},
            "structure_gate": {"passed": True},
            "multitimeframe_maturation": package,
            "multitimeframe_maturation_authority": "OBSERVATIONAL_ONLY",
        }
    ]

    result = make_paths_replayable(
        paths,
        records,
        scan_id="scan-tnon",
        scan_timestamp="2026-09-10T18:14:00+00:00",
        data_mode="Live Webull",
    )

    assert result[0]["multitimeframe_maturation"] == package
    assert result[0]["multitimeframe_maturation"] is not package
    assert result[0]["multitimeframe_maturation_authority"] == "OBSERVATIONAL_ONLY"
    assert "multitimeframe_maturation" not in paths[0]


def test_gs422_installs_after_gs421_and_does_not_touch_trading_or_audio():
    chain = open("mide/gs392_operator_order_audio.py", encoding="utf-8").read()
    source = open("mide/gs422_convergence_recorder_performance.py", encoding="utf-8").read()

    assert chain.index("install_gs421()") < chain.index("install_gs422()")
    assert "qualified_for_entry\"] =" not in source
    assert "TONE_PATTERNS" not in source
    assert "play_alert" not in source
    assert "client.bars" not in source
