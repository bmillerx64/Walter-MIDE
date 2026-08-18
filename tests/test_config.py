from mide.config import Settings


def test_from_mapping_uses_dataclass_defaults_when_unset():
    settings = Settings.from_mapping({})

    assert settings.max_price == Settings().max_price
    assert settings.max_free_float == Settings().max_free_float


def test_from_mapping_allows_overrides():
    settings = Settings.from_mapping({"MAX_PRICE": "12.5", "MAX_FREE_FLOAT": "1234567"})

    assert settings.max_price == 12.5
    assert settings.max_free_float == 1_234_567
