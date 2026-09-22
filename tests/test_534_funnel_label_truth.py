from pathlib import Path

from mide.ui import mission_control_header_markup


def test_header_funnel_labels_expansion_and_entry_ready_separately():
    html = mission_control_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="12:00:00 PM EDT",
        symbols_sampled=70,
        prefilter_count=40,
        candidate_count=15,
        focus_count=2,
        escalation_count=1,
        auto_scan="Every 60 sec",
        funnel_counts={
            "universe": 70,
            "price": 50,
            "tradability": 48,
            "free_float": 45,
            "stage_3_analysis": 45,
            "monitored": 28,
            "expansion": 15,
            "candidates": 15,
            "entry_ready": 2,
        },
    )

    assert "Expansion Assessment: 15" in html
    assert "Mission Ranking: 15" in html
    assert "Entry Ready: 2" in html
    assert "Expansion Assessment: 2" not in html


def test_runtime_funnel_count_uses_true_expansion_trace():
    source = Path("app.py").read_text(encoding="utf-8")

    assert '"expansion": int(' in source
    assert 'stage_trace.get("Expansion Assessment", {}).get("output_count", 0)' in source
    assert '"entry_ready": sum(' in source
    assert 'item.get("qualified_for_entry") is True' in source
