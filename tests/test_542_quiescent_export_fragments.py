"""GS542: export fragments poll only while background jobs are active."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_session_backup_fragment_has_running_and_quiescent_modes():
    source = _source("mide/gs496_static_session_backup.py")

    assert "polling = bool(job and job.get(\"status\") == \"running\")" in source
    assert "fragment(run_every=JOB_POLL_SECONDS)(backup_fragment)()" in source
    assert "fragment(backup_fragment)()" in source
    assert "if now_running != polling:" in source
    assert 'st.rerun(scope="app")' in source


def test_compact_bundle_fragment_has_running_and_quiescent_modes():
    source = _source("mide/gs510_compact_analysis_bundle.py")

    assert "polling = bool(job and job.get(\"status\") == \"running\")" in source
    assert (
        "fragment(run_every=JOB_POLL_SECONDS)(analysis_bundle_fragment)()"
        in source
    )
    assert "fragment(analysis_bundle_fragment)()" in source
    assert "if now_running != polling:" in source
    assert 'st.rerun(scope="app")' in source


def test_export_fragments_no_longer_run_two_second_timers_while_idle():
    backup = _source("mide/gs496_static_session_backup.py")
    compact = _source("mide/gs510_compact_analysis_bundle.py")

    assert "@fragment(run_every=JOB_POLL_SECONDS)" not in backup
    assert "@fragment(run_every=JOB_POLL_SECONDS)" not in compact


def test_gs542_does_not_change_trading_authority():
    combined = (
        _source("mide/gs496_static_session_backup.py")
        + "\n"
        + _source("mide/gs510_compact_analysis_bundle.py")
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in combined for token in forbidden)
