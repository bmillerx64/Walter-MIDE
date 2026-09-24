"""Phase 45: GS489 graduated rc105 lifecycle belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs489_webull_graduated_backoff as gs489
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_gs489_facade_delegates_graduated_backoff(monkeypatch):
    marker = object()
    monkeypatch.setattr(
        market_evidence,
        "ensure_stream_with_graduated_backoff",
        lambda original, provider, symbols, now=None: marker,
    )

    assert gs489.ensure_stream_with_graduated_backoff(
        lambda _symbols: False,
        object(),
        ["PAAI"],
    ) is marker


def test_gs489_clock_seam_remains_historical_and_mutable(monkeypatch):
    monkeypatch.setattr(
        gs489.time,
        "time",
        lambda: 1234.5,
    )
    assert gs489.time.time() == 1234.5


def test_phase45_stale_market_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs489,
        "_market",
        lambda: SimpleNamespace(),
    )

    assert gs489.install_for_provider(object()) is False


def test_phase45_market_evidence_owns_graduated_backoff():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs489_webull_graduated_backoff.py"
    ).read_text(encoding="utf-8")

    assert "def graduated_backoff_state(" in authority
    assert "def ensure_stream_with_graduated_backoff(" in authority
    assert "def install_graduated_backoff_for_provider(" in authority
    assert "gs489.time.time()" in authority
    assert '"ensure_stream_with_backoff"' in authority

    assert "def _market(" in facade
    assert "@wraps(current)" not in facade
    assert "def guarded(" not in facade


def test_phase45_scope_remains_connection_limit_retry_lifecycle_only():
    source = (
        ROOT / "mide/gs489_webull_graduated_backoff.py"
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
    assert "BACKOFF_SECONDS = (300.0, 600.0, 900.0)" in source
    assert "rest_snapshot_history_unchanged" in source
    assert '"trading_authority_changed": False' in source
