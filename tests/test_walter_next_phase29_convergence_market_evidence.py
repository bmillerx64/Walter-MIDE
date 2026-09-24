"""Phase 29: GS423 convergence handoff belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from mide import gs423_convergence_handoff_efficiency as gs423
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def _day(rows=40):
    index = pd.date_range(
        "2026-09-10 13:30:00+00:00",
        periods=rows,
        freq="min",
    )
    close = pd.Series([4.0 + i * 0.002 for i in range(rows)], index=index)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": [1000 + i * 20 for i in range(rows)],
        },
        index=index,
    )


def test_gs423_clean_runtime_delegates_to_market_evidence():
    assert gs423.AUTHORITY == market_evidence.CONVERGENCE_HANDOFF_AUTHORITY
    assert gs423.SOURCE == market_evidence.CONVERGENCE_HANDOFF_SOURCE
    assert gs423.confirmation_details_with_maturation.__name__ == (
        "confirmation_details_with_maturation"
    )
    assert gs423.build_efficient_maturation_evidence.__name__ == (
        "build_efficient_maturation_evidence"
    )


def test_gs423_warm_deploy_install_tolerates_older_market_evidence(monkeypatch):
    stale = SimpleNamespace()
    monkeypatch.setattr(gs423, "_market", lambda: stale)

    assert gs423.install() is None


def test_market_evidence_convergence_helper_preserves_observational_contract(monkeypatch):
    from mide import gs378_live_vwap_st_crossover as gs378

    day = gs378._eastern_day(_day(240))
    primary = pd.Series(4.0, index=day.index)

    def fake_supertrend(frame, period, multiplier):
        line = pd.Series(3.9, index=frame.index, dtype=float)
        trend = pd.Series(False, index=frame.index, dtype=bool)
        trend.iloc[-2:] = True
        return line, trend

    monkeypatch.setattr(gs378, "supertrend", fake_supertrend)
    count, details = market_evidence.confirmation_details_with_maturation(
        day,
        primary,
    )

    assert count == 4
    assert set(details) == {"1m", "3m", "5m", "10m"}
    assert all(item["current_confirmed"] for item in details.values())


def test_gs423_source_is_lazy_facade_not_duplicate_market_evidence():
    source = (ROOT / "mide/gs423_convergence_handoff_efficiency.py").read_text(
        encoding="utf-8"
    )

    assert "def _market(" in source
    assert "install_convergence_handoff_evidence" in source
    assert "gs378._confirmation_details =" not in source
    assert "def apply_with_efficient_maturation(" not in source
    assert "from mide.authorities import market_evidence as" not in source


def test_phase29_scope_remains_observational_only():
    source = (ROOT / "mide/gs423_convergence_handoff_efficiency.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        'record["qualified_for_entry"] =',
        'record["qualified_for_alert"] =',
        "TONE_PATTERNS",
        "play_alert",
        "place_order(",
        "submit_order(",
        "request_scan(",
        "client.bars(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)
