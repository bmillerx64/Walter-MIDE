from types import SimpleNamespace

from mide.architecture import WalterArchitectureV1
from mide.gs416_validity_symbol_suffix import install, supported_security


def test_bare_common_stock_suffix_letters_are_not_derivative_markers():
    assert supported_security({"symbol": "SNYR", "asset_status": "active"}, include_etfs=False)
    assert supported_security({"symbol": "ATER", "asset_status": "active"}, include_etfs=False)
    assert supported_security({"symbol": "ABCU", "asset_status": "active"}, include_etfs=False)


def test_explicit_derivative_evidence_still_fails_validity():
    for symbol in ("ABC-W", "ABC.R", "ABC-U"):
        assert not supported_security({"symbol": symbol, "asset_status": "active"}, include_etfs=False)
    assert not supported_security({"symbol": "SNYR", "asset_type": "right"}, include_etfs=False)
    assert not supported_security({"symbol": "ATER", "asset_type": "warrant"}, include_etfs=False)
    assert not supported_security({"symbol": "ABCU", "asset_type": "unit"}, include_etfs=False)
    assert not supported_security({"symbol": "SNYR", "exchange": "OTC"}, include_etfs=False)
    assert not supported_security({"symbol": "SNYR", "asset_status": "inactive"}, include_etfs=False)


def test_etf_policy_is_unchanged():
    record = {"symbol": "TEST", "asset_type": "etf", "asset_status": "active"}
    assert not supported_security(record, include_etfs=False)
    assert supported_security(record, include_etfs=True)


def test_live_snyr_regression_reaches_validity_as_common_stock():
    install()
    architecture = object.__new__(WalterArchitectureV1)
    architecture.policy = SimpleNamespace(include_etfs=False)
    decisions = architecture._validity(
        [
            {
                "symbol": "SNYR",
                "price": 0.1171,
                "tradable": True,
                "asset_status": "active",
                "exchange": "NASDAQ",
                "data_usable": True,
                "legally_tradable": True,
                "operationally_tradable": True,
            }
        ]
    )
    assert decisions["SNYR"].passed is True
    assert decisions["SNYR"].reason == "Valid security"


def test_gs416_does_not_rescue_actual_invalid_security():
    install()
    architecture = object.__new__(WalterArchitectureV1)
    architecture.policy = SimpleNamespace(include_etfs=False)
    decisions = architecture._validity(
        [
            {"symbol": "SNYR", "tradable": False, "asset_status": "active"},
            {"symbol": "ABC-W", "tradable": True, "asset_status": "active"},
        ]
    )
    assert decisions["SNYR"].passed is False
    assert "legally non-tradable" in decisions["SNYR"].reason
    assert decisions["ABC-W"].passed is False
    assert "unsupported security type or status" in decisions["ABC-W"].reason
