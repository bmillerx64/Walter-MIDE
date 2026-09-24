"""Phase 47: GS494 partial snapshot recovery belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs494_partial_snapshot_recovery as gs494
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_gs494_facade_delegates_partial_retry(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        market_evidence,
        "initialize_quotes_with_partial_retry",
        lambda original, provider, symbols, batch_size: marker,
    )

    assert gs494.initialize_quotes_with_partial_retry(
        lambda symbols, batch_size: {},
        object(),
        ["AAA"],
        batch_size=50,
    ) is marker


def test_gs494_install_for_provider_remains_mutable_seam(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs494,
        "install_for_provider",
        lambda provider: provider is marker,
    )
    assert gs494.install_for_provider(marker) is True


def test_phase47_stale_market_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs494,
        "_market",
        lambda: SimpleNamespace(),
    )
    assert gs494.install_for_provider(object()) is False


def test_phase47_market_evidence_owns_partial_snapshot_recovery():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs494_partial_snapshot_recovery.py"
    ).read_text(encoding="utf-8")

    assert "def partial_snapshot_symbols(" in authority
    assert "def initialize_quotes_with_partial_retry(" in authority
    assert "def install_partial_snapshot_recovery_for_provider(" in authority

    assert "def _market(" in facade
    assert "@wraps(current)" not in facade
    assert "retry = original(" not in facade


def test_phase47_scope_remains_market_data_resilience_only():
    source = (
        ROOT / "mide/gs494_partial_snapshot_recovery.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "stale_price_substitution" in source
    assert '"trading_authority_changed": False' in source
    assert "extra_provider_requests_max" in source
