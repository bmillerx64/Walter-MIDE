import config as legacy_config

from mide.config import MISSION_MAX_PRICE, Settings


def test_runtime_and_legacy_settings_share_five_dollar_ceiling(monkeypatch):
    monkeypatch.setenv("MAX_PRICE", "50")

    runtime = Settings.from_mapping({})
    legacy = legacy_config.Settings.from_mapping({})

    assert runtime.max_price == MISSION_MAX_PRICE == 5.0
    assert legacy.max_price == 5.0
    assert legacy_config.Settings is Settings


def test_price_mission_accepts_five_dollars_and_rejects_ipst_like_price():
    settings = Settings.from_mapping({})

    assert 5.00 <= settings.max_price
    assert not (12.38 <= settings.max_price)
