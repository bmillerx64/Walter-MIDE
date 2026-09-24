"""Phase 31: GS478 sparse-history sufficiency belongs to Market Evidence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from mide import gs478_sparse_history_warm_seed as gs478
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def _rows(start: datetime, count: int):
    return [
        {
            "t": start + timedelta(minutes=index),
            "o": 1.0,
            "h": 1.1,
            "l": 0.9,
            "c": 1.0,
            "v": 1000 + index,
        }
        for index in range(count)
    ]


class Client:
    @staticmethod
    def bars_frame(rows):
        frame = pd.DataFrame(rows).rename(
            columns={
                "t": "timestamp",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            }
        )
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp").sort_index()


def test_gs478_constants_match_authoritative_market_evidence():
    assert gs478.AUTHORITY == market_evidence.SPARSE_HISTORY_AUTHORITY
    assert gs478.CURRENT_REASON == market_evidence.SPARSE_HISTORY_CURRENT_REASON
    assert gs478.BRIDGE_REASON == market_evidence.SPARSE_HISTORY_BRIDGE_REASON
    assert (
        gs478.MIN_REAL_SESSION_BARS
        == market_evidence.SPARSE_HISTORY_MIN_REAL_SESSION_BARS
    )
    assert (
        gs478.LEGACY_OUTER_GATE_BARS
        == market_evidence.SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS
    )
    assert gs478.BRIDGE_LOOKBACK_DAYS == market_evidence.SPARSE_HISTORY_LOOKBACK_DAYS
    assert gs478.BRIDGE_HISTORY_BARS == market_evidence.SPARSE_HISTORY_BAR_LIMIT


def test_gs478_bridge_delegates_without_changing_12_to_19_contract():
    client = Client()
    current = _rows(datetime(2026, 9, 17, 14, 0, tzinfo=timezone.utc), 12)
    prior = _rows(datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc), 40)

    facade_rows, facade_used = gs478._bridge_rows(client, prior, current)
    authority_rows, authority_used = market_evidence.bridge_sparse_history_rows(
        client,
        prior,
        current,
    )

    assert facade_used == authority_used == 8
    assert facade_rows == authority_rows
    assert len(facade_rows) == 20


def test_gs478_warm_deploy_install_tolerates_older_market_generation(monkeypatch):
    monkeypatch.setattr(gs478, "_market", lambda: SimpleNamespace())

    assert gs478.install() is None


def test_gs478_source_is_lazy_facade_not_duplicate_analyzer_wrapper():
    source = (ROOT / "mide/gs478_sparse_history_warm_seed.py").read_text(
        encoding="utf-8"
    )

    assert "def _market(" in source
    assert "install_sparse_history_bridge" in source
    assert "def analyze_with_sparse_history_bridge(" not in source
    assert "discovery.analyze_candidates =" not in source
    assert "original_bars(" not in source
    assert "from mide.authorities import market_evidence as" not in source


def test_phase31_scope_remains_history_sufficiency_only():
    source = (ROOT / "mide/gs478_sparse_history_warm_seed.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "session_vwap(",
        "supertrend(",
        "score(",
        "execute_order",
        "place_order",
        "submit_order",
        "30Sec",
    )
    assert not any(token in source for token in forbidden)
