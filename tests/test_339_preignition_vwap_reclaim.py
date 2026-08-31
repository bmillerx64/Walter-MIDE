from mide.gs339_preignition_vwap_reclaim import Snapshot, preignition_watch, watch_recommendation


def _prior(**overrides):
    data = dict(participation=22.0, expansion=40.0, volume=300_000.0, above_vwap=False, seen_at=1.0)
    data.update(overrides)
    return Snapshot(**data)


def _record(**overrides):
    data = {
        "symbol": "VBIO",
        "vwap_distance_pct": 1.2,
        "supertrend_bullish": True,
        "participation_score": 32,
        "expansion_score": 46,
        "volume": 360_000,
    }
    data.update(overrides)
    return data


def test_vbio_like_reclaim_surfaces_watch_close_cue():
    ok, reason = preignition_watch(_record(), _prior())
    assert ok is True
    assert "VWAP" in reason
    rec = watch_recommendation(_record(), _prior())
    assert rec["label"] == "SETUP BUILDING · WATCH CLOSELY"


def test_below_vwap_is_rejected():
    ok, reason = preignition_watch(_record(vwap_distance_pct=-1.0), _prior())
    assert ok is False
    assert reason == "below VWAP"


def test_extended_move_is_not_preignition():
    ok, reason = preignition_watch(_record(vwap_distance_pct=4.0), _prior())
    assert ok is False
    assert reason == "too extended"


def test_low_participation_sora_like_case_is_rejected():
    ok, reason = preignition_watch(_record(participation_score=14, expansion_score=47), _prior())
    assert ok is False
    assert reason == "participation too weak"


def test_low_volume_without_catalyst_is_rejected():
    ok, reason = preignition_watch(_record(volume=64_000), _prior(volume=60_000))
    assert ok is False
    assert reason == "volume too light without catalyst"


def test_fresh_catalyst_allows_lower_absolute_volume():
    ok, _ = preignition_watch(_record(volume=64_000, headline="Fresh company update"), _prior(volume=60_000))
    assert ok is True


def test_static_good_scores_do_not_repeat_watch_without_reclaim():
    prior = _prior(participation=32, expansion=46, above_vwap=True, volume=350_000)
    ok, reason = preignition_watch(_record(volume=360_000), prior)
    assert ok is False
    assert reason == "no fresh reclaim or strengthening"
