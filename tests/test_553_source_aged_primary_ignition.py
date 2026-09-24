"""GS553: primary ignition uses operator-time source freshness."""

from pathlib import Path

from mide import gs553_source_aged_primary_ignition as gs553
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def _record(
    symbol="TEST",
    *,
    bar_age=30.0,
    reclaim_age=0,
    reclaimed=True,
    distance=1.0,
    flip_age=900.0,
):
    return {
        "symbol": symbol,
        "bar_age_seconds": bar_age,
        "vwap_relation": "above",
        "vwap_distance_pct": distance,
        "vwap_reclaimed_last_10m": reclaimed,
        "vwap_reclaim_age_bars": reclaim_age,
        "supertrend_flip_age_seconds": flip_age,
        "participation_score": 45.0,
        "expansion_quality": 58.0,
        "timeframes": {
            "1m": {
                "supertrend": True,
                "above_vwap": True,
                "bullish_flip_age_seconds": flip_age,
                "freshness_authority": (
                    market_evidence.GS548_MATURATION_FRESHNESS_AUTHORITY
                ),
            },
            "3m": {
                "supertrend": False,
                "above_vwap": True,
            },
        },
    }


def test_gs553_same_bar_reclaim_zero_is_not_discarded():
    # Mirrors SPHL in the 2026-09-24 CAB: same-bar reclaim, source age 97.8s,
    # price within the +2% guard, bullish 1m ST, and supporting flow.
    record = _record(
        "SPHL",
        bar_age=97.8,
        reclaim_age=0,
        reclaimed=True,
        distance=1.1554,
        flip_age=697.8,
    )

    evidence = market_evidence.ignition_evidence(record)

    assert evidence["vwap_reclaim_age_bars"] == 0.0
    assert evidence["vwap_reclaim_effective_age_seconds"] == 97.8
    assert evidence["vwap_reclaim_recent"] is True
    assert evidence["recent"] is True
    assert evidence["trigger"] == "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
    assert evidence["freshness_authority"] == gs553.AUTHORITY


def test_gs553_stale_source_bar_cannot_masquerade_as_fresh_reclaim():
    # Mirrors RPGL in the CAB: a one-bar reclaim was still called recent while
    # the newest source bar was more than ten minutes old.
    record = _record(
        "RPGL",
        bar_age=644.5,
        reclaim_age=1,
        reclaimed=True,
        distance=1.9832,
        flip_age=12704.5,
    )

    evidence = market_evidence.ignition_evidence(record)

    assert evidence["vwap_reclaim_source_relative_age_seconds"] == 60.0
    assert evidence["vwap_reclaim_effective_age_seconds"] == 704.5
    assert evidence["vwap_reclaim_recent"] is False
    assert evidence["one_minute_bullish_flip_recent"] is False
    assert evidence["recent"] is False
    assert evidence["trigger"] is None


def test_gs553_prefers_gs548_corrected_one_minute_flip_age():
    record = _record(
        bar_age=700.0,
        reclaim_age=999,
        reclaimed=False,
        flip_age=300.0,
    )
    # Top-level raw data can disagree with the corrected timeframe detail on
    # retained records. The GS548-tagged detail is the operator-time authority.
    record["supertrend_flip_age_seconds"] = 0.0

    evidence = market_evidence.ignition_evidence(record)

    assert evidence["one_minute_bullish_flip_age_seconds"] == 300.0
    assert evidence["one_minute_bullish_flip_recent"] is False
    assert evidence["recent"] is False


def test_gs553_warm_facade_repairs_retained_legacy_function(monkeypatch):
    def legacy(_record):
        return {
            "recent": False,
            "trigger": None,
            "inside_chase_guard": True,
            "one_minute_supertrend_bullish": True,
            "one_minute_above_vwap": True,
            "vwap_reclaim_recent": False,
            "vwap_reclaim_age_bars": 999.0,
            "one_minute_bullish_flip_recent": False,
            "one_minute_bullish_flip_age_seconds": 900.0,
            "supporting_flow": ["participation 45"],
        }

    monkeypatch.setattr(market_evidence, "ignition_evidence", legacy)

    assert gs553.install() is True
    evidence = market_evidence.ignition_evidence(
        _record(bar_age=90.0, reclaim_age=0, reclaimed=True)
    )

    assert evidence["vwap_reclaim_age_bars"] == 0.0
    assert evidence["vwap_reclaim_recent"] is True
    assert evidence["trigger"] == "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
    assert evidence["freshness_authority"] == gs553.AUTHORITY


def test_gs553_app_installs_warm_facade_before_dashboard_runtime():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    bind = source.index("mide.gs553_source_aged_primary_ignition")
    sidebar = source.index("with st.sidebar:")

    assert bind < sidebar
    assert ").install()" in source[bind:bind + 300]


def test_gs553_scope_is_freshness_and_operator_attention_only():
    source = (
        ROOT / "mide/gs553_source_aged_primary_ignition.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
