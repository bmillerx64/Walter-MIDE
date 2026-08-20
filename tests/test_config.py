import config as legacy_config

from mide.config import MISSION_MAX_PRICE, MISSION_MIN_PRICE, Settings


def test_from_mapping_uses_dataclass_defaults_when_unset():
    settings = Settings.from_mapping({})

    assert settings.min_price == MISSION_MIN_PRICE == 0.02
    assert settings.max_price == MISSION_MAX_PRICE == 5.0
    assert settings.max_free_float == Settings().max_free_float


def test_from_mapping_allows_safe_overrides_but_cannot_expand_price_mission():
    settings = Settings.from_mapping(
        {"MIN_PRICE": "0.50", "MAX_PRICE": "12.5", "MAX_FREE_FLOAT": "1234567"}
    )

    assert settings.min_price == 0.50
    assert settings.max_price == 5.0
    assert settings.max_free_float == 1_234_567


def test_stale_environment_cannot_reintroduce_fifty_dollar_candidates(monkeypatch):
    monkeypatch.setenv("MAX_PRICE", "50")

    assert Settings.from_mapping({}).max_price == 5.0


def test_legacy_config_is_the_same_authoritative_settings_contract():
    assert legacy_config.Settings is Settings
    assert legacy_config.MISSION_MIN_PRICE == MISSION_MIN_PRICE
    assert legacy_config.MISSION_MAX_PRICE == MISSION_MAX_PRICE
