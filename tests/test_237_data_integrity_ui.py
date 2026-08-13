from mide.data_integrity import (
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_FAILURE,
    STATUS_HEALTHY,
)
from mide.ui import data_integrity_markup


def test_scan_trust_markup_renders_all_statuses_and_scores():
    for status, icon, score in (
        (STATUS_HEALTHY, "🟢", 100),
        (STATUS_EMPTY, "🔵", 100),
        (STATUS_DEGRADED, "🟠", 96),
        (STATUS_FAILURE, "🔴", 52),
    ):
        markup = data_integrity_markup(
            {
                "status": status,
                "trust_score": score,
                "record_integrity_pct": 99,
                "freshness_pct": None,
                "unique_symbols": 2,
                "record_count": 3,
                "status_reason": "Diagnostic only.",
            }
        )
        assert f"{icon} SCAN TRUST — {status} · {score}%" in markup
        assert "Integrity</span><b>99%" in markup
        assert "Freshness</span><b>N/A" in markup
        assert "2 / 3" in markup
