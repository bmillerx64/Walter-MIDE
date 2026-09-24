"""Phase 32: GS459 price trajectory is split by authoritative responsibility."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from mide import gs459_price_trajectory_attention as gs459
from mide.authorities import market_evidence, presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _frame():
    closes = [
        1.000, 1.002, 1.004, 1.006, 1.008, 1.010,
        1.012, 1.020, 1.035, 1.055, 1.080,
    ]
    index = pd.date_range(
        "2026-09-15 14:00",
        periods=len(closes),
        freq="1min",
        tz="UTC",
    )
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value * 1.002 for value in closes],
            "low": [value * 0.998 for value in closes],
            "close": closes,
            "volume": [100_000] * len(closes),
        },
        index=index,
    )


def test_gs459_market_metrics_delegate_to_market_evidence():
    facade = gs459.price_trajectory_metrics(_frame())
    authority = market_evidence.price_trajectory_metrics(_frame())

    assert facade == authority
    assert facade["price_trajectory_available"] is True
    assert facade["price_path_acceleration_pct_per_min"] > 1.0


def test_gs459_attention_delegates_to_presentation_audio(monkeypatch):
    from mide import gs310_unified_opportunity_state as unified

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {"state": unified.DEVELOPING},
    )
    record = {
        "price_trajectory_available": True,
        "price_change_3m_pct": 2.4,
        "price_change_5m_path_pct": 3.1,
        "price_path_acceleration_pct_per_min": 0.45,
        "positive_close_ratio_5m": 0.8,
        "giveback_from_5m_high_pct": 0.4,
        "volume_acceleration_3m": 1.6,
        "dollar_flow_acceleration_3m": 1.4,
        "higher_lows": True,
        "near_hod": True,
    }

    assert gs459.trajectory_attention(record) == presentation_audio.trajectory_attention(record)
    assert gs459.trajectory_attention(record)["active"] is True


def test_gs459_downstream_monkeypatch_seam_survives_authority_split(monkeypatch):
    from mide import gs457_maturation_leader_priority as gs457

    records = [{"symbol": "BASE"}, {"symbol": "TRAJ"}]
    monkeypatch.setattr(
        gs457,
        "maturation_attention",
        lambda record: {"band": 30},
    )
    monkeypatch.setattr(
        gs459,
        "trajectory_attention",
        lambda record: {
            "active": record["symbol"] == "TRAJ",
            "acceleration_pct_per_min": 0.8,
            "change_3m_pct": 2.0,
            "positive_close_ratio_5m": 0.8,
        },
    )

    ordered = gs459.ordered_trajectory_records(
        records,
        baseline_order=lambda rows: list(rows),
    )

    assert [record["symbol"] for record in ordered] == ["TRAJ", "BASE"]


def test_gs459_install_tolerates_stale_authority_generations(monkeypatch):
    monkeypatch.setattr(gs459, "_market", lambda: SimpleNamespace())
    monkeypatch.setattr(gs459, "_presentation", lambda: SimpleNamespace())

    assert gs459.install() is None


def test_gs459_source_is_lazy_split_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs459_price_trajectory_attention.py").read_text(
        encoding="utf-8"
    )

    assert "def _market(" in source
    assert "def _presentation(" in source
    assert "install_price_trajectory_metrics" in source
    assert "install_price_trajectory_presentation" in source
    assert "def intraday_participation_metrics(" not in source
    assert "def ordered_escalation_records(" not in source
    assert "recent_closes.diff()" not in source
    assert "from mide.authorities import market_evidence as" not in source
    assert "from mide.authorities import presentation_audio as" not in source


def test_phase32_scope_remains_attention_only():
    source = (ROOT / "mide/gs459_price_trajectory_attention.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "TRIGGER_",
        "PARTICIPATION_MIN_",
        "client.bars(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)
