from mide import gs525_fresh_attention_expiry as gs525
from mide.authorities import thesis_state


def _view():
    return {
        "state": "DEVELOPING",
        "color": "blue",
        "reason": "Current 1m VWAP/SuperTrend ignition is worth monitoring.",
        "next_step": "Keep it visible.",
        "look_now_semantics": {
            "legacy_1m_ignition_demoted": True,
            "bottom_up_compression": False,
            "jet_fuel": False,
        },
    }


def test_stale_legacy_developing_gets_late_continuation_language(monkeypatch):
    record = {"supertrend_30s_last_flip_age_seconds": 13 * 60}
    monkeypatch.setattr(thesis_state, "fresh_higher_maturation", lambda _record: False)

    result = gs525.tightened_opportunity_state(lambda _record: _view(), record)

    assert result["state"] == "DEVELOPING"
    assert result["reason"].startswith("LATE CONTINUATION WATCH:")
    assert "13.0 minutes old" in result["reason"]
    assert result["freshness_semantics"]["late_legacy_ignition"] is True


def test_five_minute_or_fresher_ignition_keeps_existing_semantics(monkeypatch):
    record = {"supertrend_30s_last_flip_age_seconds": 4 * 60}
    monkeypatch.setattr(thesis_state, "fresh_higher_maturation", lambda _record: False)

    result = gs525.tightened_opportunity_state(lambda _record: _view(), record)

    assert result == _view()


def test_fresh_higher_maturation_rearms_old_runner(monkeypatch):
    record = {"supertrend_30s_last_flip_age_seconds": 13 * 60}
    monkeypatch.setattr(thesis_state, "fresh_higher_maturation", lambda _record: True)

    result = gs525.tightened_opportunity_state(lambda _record: _view(), record)

    assert result == _view()


def test_non_legacy_developing_is_untouched(monkeypatch):
    record = {"supertrend_30s_last_flip_age_seconds": 13 * 60}
    view = _view()
    view["look_now_semantics"]["legacy_1m_ignition_demoted"] = False
    monkeypatch.setattr(thesis_state, "fresh_higher_maturation", lambda _record: False)

    result = gs525.tightened_opportunity_state(lambda _record: view, record)

    assert result == view


def test_install_tightens_only_preflip_freshness_constant():
    from mide import gs462_preflip_ignition_watch as gs462

    original = gs462.RECENT_30S_FLIP_SECONDS
    try:
        gs525.install()
        assert gs462.RECENT_30S_FLIP_SECONDS == 300.0
    finally:
        gs462.RECENT_30S_FLIP_SECONDS = original
