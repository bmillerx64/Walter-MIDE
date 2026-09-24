"""Phase 35: GS464 VWAP truth splits across Market Evidence and Replay Validation."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from mide import gs464_session_aware_vwap_parity as gs464
from mide.authorities import market_evidence, replay_validation


ROOT = Path(__file__).resolve().parents[1]


def _frame():
    index = pd.DatetimeIndex(
        [
            "2026-09-16 08:00",
            "2026-09-16 09:29",
            "2026-09-16 09:30",
            "2026-09-16 09:31",
        ],
        tz="America/New_York",
    )
    return pd.DataFrame(
        {
            "open": [1.0, 1.0, 0.8, 0.82],
            "high": [1.0, 1.0, 0.8, 0.82],
            "low": [1.0, 1.0, 0.8, 0.82],
            "close": [1.0, 1.0, 0.8, 0.82],
            "volume": [1_000_000, 1_000_000, 100, 100],
        },
        index=index,
    )


def test_gs464_primary_context_delegates_to_market_evidence():
    facade = gs464.session_aware_primary_vwap_context(_frame())
    authority = market_evidence.session_aware_primary_vwap_context(
        _frame()
    )

    assert facade["session_policy"] == gs464.SESSION_POLICY
    assert facade["anchor_mode"] == gs464.RTH_POLICY
    assert facade["value"] == authority["value"]
    assert facade["extended_value"] == authority["extended_value"]


def test_gs464_market_install_tolerates_stale_generation(monkeypatch):
    monkeypatch.setattr(gs464, "_market", lambda: SimpleNamespace())

    assert gs464._install_primary_authority() is None
    assert gs464._install_record_diagnostics() is None


def test_gs464_replay_install_tolerates_stale_generation(monkeypatch):
    monkeypatch.setattr(gs464, "_replay", lambda: SimpleNamespace())

    assert gs464._install_recorder_policy_label() is None


def test_phase35_facade_is_lazy_split_not_duplicate_implementation():
    source = (
        ROOT / "mide/gs464_session_aware_vwap_parity.py"
    ).read_text(encoding="utf-8")

    assert "def _market(" in source
    assert "def _replay(" in source
    assert "install_session_aware_primary_vwap" in source
    assert "install_session_aware_vwap_parity_labels" in source
    assert "def apply_session_aware_truth(" not in source
    assert "def build_scan_parity(" not in source
    assert "session_vwap(anchored)" not in source


def test_phase35_authority_ownership_is_explicit():
    market_source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    replay_source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def session_aware_primary_vwap_context(" in market_source
    assert "def install_session_aware_vwap_evidence(" in market_source
    assert "def install_session_aware_vwap_parity_labels(" in replay_source


def test_phase35_scope_preserves_zero_request_and_no_trading_authority():
    source = (
        ROOT / "mide/gs464_session_aware_vwap_parity.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        ".get_bars(",
        ".history(",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "PARTICIPATION_MIN_",
    )
    assert not any(token in source for token in forbidden)
    assert '"additional_market_data_requests": 0' in source
