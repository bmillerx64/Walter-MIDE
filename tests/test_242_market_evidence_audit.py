from datetime import datetime, timezone

from mide.market_evidence_audit import market_evidence_report, market_evidence_summary


def _record(**overrides):
    base = {
        "symbol": "TEST",
        "price": 1.25,
        "volume": 250000,
        "vwap_value": 1.20,
        "supertrend_bullish": True,
        "source_bar_timestamp": "2026-08-13T20:00:00+00:00",
        "timeframes": {"1m": {"ok": True}},
    }
    base.update(overrides)
    return base


def test_complete_fresh_evidence_is_trusted():
    report = market_evidence_report(_record(), scan_timestamp=datetime(2026, 8, 13, 20, 0, 30, tzinfo=timezone.utc))
    assert report["status"] == "TRUSTED"
    assert report["trusted"] is True
    assert report["completeness_pct"] == 100.0
    assert report["fresh"] is True


def test_stale_evidence_is_caution_not_trusted():
    report = market_evidence_report(_record(), scan_timestamp=datetime(2026, 8, 13, 20, 5, 0, tzinfo=timezone.utc))
    assert report["status"] == "CAUTION"
    assert report["trusted"] is False
    assert report["fresh"] is False


def test_missing_decision_evidence_is_visible_and_insufficient():
    report = market_evidence_report(_record(vwap_value=None, supertrend_bullish=None), scan_timestamp="2026-08-13T20:00:30+00:00")
    assert report["status"] == "INSUFFICIENT"
    assert report["trusted"] is False
    assert "vwap_value" in report["missing_fields"]
    assert "supertrend_bullish" in report["missing_fields"]


def test_bad_numeric_evidence_is_insufficient():
    report = market_evidence_report(_record(price=-1), scan_timestamp="2026-08-13T20:00:30+00:00")
    assert report["status"] == "INSUFFICIENT"
    assert "price_nonpositive" in report["coherence_failures"]


def test_summary_surfaces_status_completeness_and_age():
    text = market_evidence_summary(_record(), scan_timestamp="2026-08-13T20:00:30+00:00")
    assert "TRUSTED" in text
    assert "100%" in text
    assert "age 30s" in text
