"""Phase 44: GS488 splits provider lifecycle and replay trace authorities."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs488_webull_connection_limit_backoff as gs488
from mide.authorities import market_evidence, replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs488_facade_delegates_backoff_snapshot(monkeypatch):
    marker = {"active": True}
    monkeypatch.setattr(
        market_evidence,
        "connection_limit_backoff_snapshot",
        lambda provider, now=None: marker,
    )

    assert gs488.backoff_snapshot(object()) is marker


def test_gs488_install_for_provider_remains_mutable_seam(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        gs488,
        "install_for_provider",
        lambda provider: provider is marker,
    )

    assert gs488.install_for_provider(marker) is True


def test_phase44_stale_authority_generations_are_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs488,
        "_market",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs488,
        "_replay",
        lambda: SimpleNamespace(),
    )

    assert gs488.install_for_provider(object()) is False
    assert gs488.install() is None


def test_phase44_market_evidence_preserves_gs489_upgrade_global():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def ensure_stream_with_backoff(" in source
    assert "def install_for_provider(" in source
    assert '"ensure_stream_with_backoff"' in source
    assert "def install_connection_limit_market_evidence(" in source


def test_phase44_replay_owns_stream_trace_only():
    source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def install_connection_limit_stream_trace(" in source
    assert '"connection_limit_backoff"' in source
    assert '"gs488_connection_limit_containment"' in source


def test_phase44_facade_no_longer_owns_wrapper_implementation():
    source = (
        ROOT / "mide/gs488_webull_connection_limit_backoff.py"
    ).read_text(encoding="utf-8")

    assert "def _market(" in source
    assert "def _replay(" in source
    assert "@wraps(current)" not in source
    assert "def guarded(" not in source


def test_phase44_scope_remains_stream_retry_lifecycle_only():
    source = (
        ROOT / "mide/gs488_webull_connection_limit_backoff.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "COOLDOWN_SECONDS = 300.0" in source
    assert "BACKOFF_SECONDS = (300.0, 600.0, 900.0)" in source
    assert "REVISION = 2" in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
