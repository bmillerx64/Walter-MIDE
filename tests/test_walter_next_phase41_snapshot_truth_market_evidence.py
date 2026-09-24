"""Phase 41: GS475/476 snapshot truth belongs to Market Evidence."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from mide import gs475_premarket_snapshot_truth as gs475
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")


def test_gs475_facade_delegates_snapshot_overlay():
    payload = {
        "data": [{
            "symbol": "HOT",
            "price": "1.00",
            "ext_price": "2.00",
            "ext_trade_time": 200,
        }]
    }
    result = gs475.apply_snapshot_session_truth(
        payload,
        now_et=datetime(
            2026,
            9,
            17,
            8,
            0,
            tzinfo=ET,
        ),
    )
    assert result["data"][0]["price"] == "2.00"
    assert (
        result["data"][0]["_walter_snapshot_session"]
        == "PRE"
    )


def test_phase41_clock_seam_remains_historical_and_mutable(monkeypatch):
    marker = datetime(
        2026,
        9,
        17,
        10,
        0,
        tzinfo=ET,
    )
    monkeypatch.setattr(
        gs475,
        "_now_eastern",
        lambda: marker,
    )
    assert gs475._now_eastern() is marker


def test_phase41_install_tolerates_stale_market_generation(monkeypatch):
    monkeypatch.setattr(
        gs475,
        "_market",
        lambda: SimpleNamespace(),
    )
    assert gs475.install() is None


def test_phase41_authority_owns_snapshot_truth():
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs475_premarket_snapshot_truth.py"
    ).read_text(encoding="utf-8")

    assert "def apply_snapshot_session_truth(" in authority
    assert "def extended_snapshot_without_overnight(" in authority
    assert "def install_snapshot_session_truth(" in authority
    assert "extend_hour_required=True" in authority

    assert "def _market(" in facade
    assert "def stock_snapshot_with_session_truth(" not in facade


def test_phase41_scope_remains_source_price_truth_only():
    source = (
        ROOT / "mide/gs475_premarket_snapshot_truth.py"
    ).read_text(encoding="utf-8")

    assert "separately entitled overnight snapshot flag is deliberately never requested" in source
    assert "extend_hour_required=True" in source
    assert "ext_price" in source
    assert "scanner_v2" not in source
    assert "trader_priority_sort_key" not in source
    assert "qualified_for_entry =" not in source
    assert "qualified_for_alert =" not in source
