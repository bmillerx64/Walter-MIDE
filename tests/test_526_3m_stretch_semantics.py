from mide import gs526_3m_stretch_semantics as gs526


def _developing_view():
    return {
        "state": "DEVELOPING",
        "color": "#60a5fa",
        "reason": "Constructive price/trend structure is present.",
        "next_step": "Need stronger participation.",
        "attention_provenance": [],
        "evidence": [],
    }


def _truth(gap):
    return {
        "state": "NOT_AT_3M_ST_YET",
        "three_minute_bullish": True,
        "signed_gap_pct": gap,
        "price": 0.7539,
        "three_minute_supertrend": 0.6408,
    }


def test_gels_like_3m_stretch_becomes_chase_wait(monkeypatch):
    monkeypatch.setattr(gs526.gs493, "three_minute_st_retest_truth", lambda _r: _truth(15.0))
    monkeypatch.setattr(gs526, "fresh_higher_maturation", lambda _r: False)

    result = gs526.tightened_opportunity_state(lambda _r: _developing_view(), {})

    assert result["state"] == "CHASE / WAIT"
    assert "15.0% above" in result["reason"]
    assert result["three_minute_stretch_semantics"]["authority"] == "PRESENTATION_ONLY"


def test_small_3m_gap_keeps_developing(monkeypatch):
    monkeypatch.setattr(gs526.gs493, "three_minute_st_retest_truth", lambda _r: _truth(4.9))
    monkeypatch.setattr(gs526, "fresh_higher_maturation", lambda _r: False)

    result = gs526.tightened_opportunity_state(lambda _r: _developing_view(), {})

    assert result == _developing_view()


def test_fresh_higher_maturation_rearms_large_gap(monkeypatch):
    monkeypatch.setattr(gs526.gs493, "three_minute_st_retest_truth", lambda _r: _truth(15.0))
    monkeypatch.setattr(gs526, "fresh_higher_maturation", lambda _r: True)

    result = gs526.tightened_opportunity_state(lambda _r: _developing_view(), {})

    assert result == _developing_view()


def test_non_developing_state_is_untouched(monkeypatch):
    view = _developing_view()
    view["state"] = "LOOK NOW"
    monkeypatch.setattr(gs526.gs493, "three_minute_st_retest_truth", lambda _r: _truth(15.0))
    monkeypatch.setattr(gs526, "fresh_higher_maturation", lambda _r: False)

    result = gs526.tightened_opportunity_state(lambda _r: view, {})

    assert result == view
