from mide.gs339_preignition_vwap_reclaim import (
    MAX_VWAP_DISTANCE_PCT,
    MIN_EXPANSION,
    MIN_PARTICIPATION,
)


def test_gs339_thresholds_remain_conservative():
    assert MAX_VWAP_DISTANCE_PCT == 2.5
    assert MIN_PARTICIPATION == 28.0
    assert MIN_EXPANSION == 45.0
