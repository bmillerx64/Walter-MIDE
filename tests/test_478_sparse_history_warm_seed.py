from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from mide import discovery
from mide import gs478_sparse_history_warm_seed as gs478


NOW = datetime(2026, 9, 17, 14, 15, tzinfo=timezone.utc)
SESSION_START = datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc)


def _rows(start: datetime, count: int, *, price: float = 1.0, volume: int = 1000):
    return [
        {
            "t": start + timedelta(minutes=index),
            "o": price,
            "h": price + 0.02,
            "l": price - 0.02,
            "c": price + index / 10_000,
            "v": volume + index,
        }
        for index in range(count)
    ]


class FakeClient:
    def __init__(self, current_count: int):
        self.current = _rows(NOW - timedelta(minutes=current_count - 1), current_count, price=2.0)
        self.prior = _rows(datetime(2026, 9, 16, 13, 30, tzinfo=timezone.utc), 40, price=1.0)
        self.calls = []
        self.diagnostics = {}
        self.warnings = []

    def bars(self, symbols, **kwargs):
        reason = kwargs.get("history_reason")
        self.calls.append((tuple(symbols), reason, kwargs.get("limit")))
        if reason == gs478.CURRENT_REASON:
            return {symbol: list(self.current) for symbol in symbols}
        if reason == gs478.BRIDGE_REASON:
            return {symbol: list(self.prior) for symbol in symbols}
        if reason == "stage6_historical_profile":
            return {symbol: list(self.prior) for symbol in symbols}
        return {symbol: [] for symbol in symbols}

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


def _fake_stage6(client, candidates, _news, _reasons):
    symbols = [item["symbol"] for item in candidates]
    raw = client.bars(
        symbols,
        start=SESSION_START,
        timeframe="1Min",
        limit=960,
        force_batch=True,
        history_reason=gs478.CURRENT_REASON,
    )
    output = []
    for symbol in symbols:
        frame = client.bars_frame(raw.get(symbol) or [])
        if len(frame) < gs478.LEGACY_OUTER_GATE_BARS:
            continue
        latest_date = frame.index[-1].date()
        session = frame[frame.index.date == latest_date].copy()
        if len(session) < gs478.MIN_REAL_SESSION_BARS:
            session = frame.tail(150).copy()
        output.append(
            {
                "symbol": symbol,
                "total_rows_seen_by_legacy_gate": len(frame),
                "current_session_rows_used": len(session),
                "first_session_timestamp": session.index[0].isoformat(),
            }
        )
    return output


def test_bridge_prepends_only_minimum_real_prior_rows():
    client = FakeClient(12)
    merged, used = gs478._bridge_rows(client, client.prior, client.current)

    assert used == 8
    assert len(merged) == 20
    frame = client.bars_frame(merged)
    latest_date = frame.index[-1].date()
    assert len(frame[frame.index.date == latest_date]) == 12


def test_under_twelve_real_session_bars_are_not_bridged():
    client = FakeClient(11)
    merged, used = gs478._bridge_rows(client, client.prior, client.current)

    assert used == 0
    assert merged == client.current


def test_twenty_or_more_real_session_bars_need_no_bridge():
    client = FakeClient(20)
    merged, used = gs478._bridge_rows(client, client.prior, client.current)

    assert used == 0
    assert merged == client.current


def test_install_admits_12_bar_mover_without_leaking_prior_rows_into_session(monkeypatch):
    client = FakeClient(12)
    monkeypatch.setattr(discovery, "analyze_candidates", _fake_stage6)

    gs478.install()
    records = discovery.analyze_candidates(client, [{"symbol": "PAAI"}], {}, {})

    assert len(records) == 1
    assert records[0]["symbol"] == "PAAI"
    assert records[0]["total_rows_seen_by_legacy_gate"] == 20
    assert records[0]["current_session_rows_used"] == 12
    # The session handed to analysis begins on Sep. 17, never on the prior seed date.
    assert "2026-09-17" in records[0]["first_session_timestamp"]
    assert [reason for _symbols, reason, _limit in client.calls] == [
        gs478.CURRENT_REASON,
        gs478.BRIDGE_REASON,
    ]
    detail = client.diagnostics["gs478_sparse_history_bridge"]
    assert detail["sparse_current_bar_counts"] == {"PAAI": 12}
    assert detail["bridged_prior_rows"] == {"PAAI": 8}
    assert detail["synthetic_bars"] == 0
    assert detail["volume_profile_contract_changed"] is False
    assert detail["trading_logic_changed"] is False


def test_install_refuses_11_bar_mover_instead_of_manufacturing_evidence(monkeypatch):
    client = FakeClient(11)
    monkeypatch.setattr(discovery, "analyze_candidates", _fake_stage6)

    gs478.install()
    records = discovery.analyze_candidates(client, [{"symbol": "TOOEARLY"}], {}, {})

    assert records == []
    assert [reason for _symbols, reason, _limit in client.calls] == [gs478.CURRENT_REASON]
    detail = client.diagnostics["gs478_sparse_history_bridge"]
    assert detail["below_safe_minimum_counts"] == {"TOOEARLY": 11}
    assert detail["bridge_history_requests"] == 0


def test_dense_history_path_is_byte_for_byte_untouched_at_provider_boundary(monkeypatch):
    client = FakeClient(25)
    original_rows = list(client.current)
    monkeypatch.setattr(discovery, "analyze_candidates", _fake_stage6)

    gs478.install()
    records = discovery.analyze_candidates(client, [{"symbol": "DENSE"}], {}, {})

    assert records[0]["total_rows_seen_by_legacy_gate"] == 25
    assert client.current == original_rows
    assert [reason for _symbols, reason, _limit in client.calls] == [gs478.CURRENT_REASON]
    assert client.diagnostics["gs478_sparse_history_bridge"]["bridged_prior_rows"] == {}


def test_startup_binds_gs478_between_warm_cache_and_latency_recorder():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs478_sparse_history_warm_seed" in source
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs424()") < body.index("install_gs478()") < body.index("install_gs425()")


def test_gs478_scope_lock_is_history_sufficiency_only():
    source = Path("mide/gs478_sparse_history_warm_seed.py").read_text(encoding="utf-8")
    assert "MIN_REAL_SESSION_BARS = 12" in source
    assert "LEGACY_OUTER_GATE_BARS = 20" in source
    assert '"timeframe": "1Min"' in source
    assert "30Sec" not in source
    assert "qualified_for_entry =" not in source
    assert "qualified_for_alert =" not in source
    assert "session_vwap(" not in source
    assert "supertrend(" not in source
    assert "score(" not in source
    assert "execute_order" not in source
    assert "place_order" not in source
