from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs369_escalation_priority_order as gs369
from mide import gs497_rank_aware_attention_order as gs497


def _record(symbol, state, rank=None, *, terminal_stage=None, terminal_outcome=None):
    row = {"symbol": symbol, "_state": state}
    if rank is not None:
        row["mission_rank"] = rank
    if terminal_stage is not None:
        row["terminal_stage"] = terminal_stage
    if terminal_outcome is not None:
        row["terminal_outcome"] = terminal_outcome
    return row


def _patch_state(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["_state"], "reason": "test"},
    )


def test_sept18_ncra_ztg_case_uses_existing_mission_rank(monkeypatch):
    _patch_state(monkeypatch)
    ncra = _record(
        "NCRA",
        unified.LOOK_NOW,
        11,
        terminal_stage="Mission Ranking and Publication",
        terminal_outcome="Qualified and Ranked",
    )
    ztg = _record(
        "ZTG",
        unified.CHASE_WAIT,
        2,
        terminal_stage="Mission Ranking and Publication",
        terminal_outcome="Qualified and Ranked",
    )

    baseline = lambda rows: [ncra, ztg]
    ordered = gs497.ordered_rank_aware_records([ncra, ztg], baseline_order=baseline)

    assert [row["symbol"] for row in ordered] == ["ZTG", "NCRA"]
    assert unified.opportunity_state(ordered[0])["state"] == unified.CHASE_WAIT
    assert unified.opportunity_state(ordered[1])["state"] == unified.LOOK_NOW


def test_watch_for_entry_remains_absolute_first(monkeypatch):
    _patch_state(monkeypatch)
    ready = _record("READY", unified.WATCH_FOR_ENTRY, 12)
    chase = _record("LEADER", unified.CHASE_WAIT, 1)
    look = _record("LOOK", unified.LOOK_NOW, 2)

    ordered = gs497.ordered_rank_aware_records(
        [look, chase, ready],
        baseline_order=lambda rows: [ready, look, chase],
    )

    assert [row["symbol"] for row in ordered] == ["READY", "LEADER", "LOOK"]


def test_unranked_records_keep_gs465_state_contiguous_fallback(monkeypatch):
    _patch_state(monkeypatch)
    look = _record("LOOK", unified.LOOK_NOW)
    dev = _record("DEV", unified.DEVELOPING)
    chase = _record("CHASE", unified.CHASE_WAIT)
    baseline = [look, dev, chase]

    ordered = gs497.ordered_rank_aware_records(
        list(reversed(baseline)),
        baseline_order=lambda rows: list(baseline),
    )

    assert ordered == baseline


def test_stale_rank_from_pre_ranking_terminal_stage_is_ignored(monkeypatch):
    _patch_state(monkeypatch)
    stale = _record(
        "STALE",
        unified.CHASE_WAIT,
        1,
        terminal_stage="Expansion Assessment",
        terminal_outcome="Rejected",
    )
    look = _record("LOOK", unified.LOOK_NOW)

    assert gs497.current_mission_rank(stale) is None
    ordered = gs497.ordered_rank_aware_records(
        [stale, look],
        baseline_order=lambda rows: [look, stale],
    )
    assert [row["symbol"] for row in ordered] == ["LOOK", "STALE"]


def test_equal_rank_preserves_existing_state_attention_tie_behavior(monkeypatch):
    _patch_state(monkeypatch)
    look = _record("LOOK", unified.LOOK_NOW, 3)
    chase = _record("CHASE", unified.CHASE_WAIT, 3)

    ordered = gs497.ordered_rank_aware_records(
        [chase, look],
        baseline_order=lambda rows: [look, chase],
    )

    assert [row["symbol"] for row in ordered] == ["LOOK", "CHASE"]


def test_halted_remains_last_even_with_rank(monkeypatch):
    _patch_state(monkeypatch)
    halt = _record("HALT", unified.HALTED, 1)
    dev = _record("DEV", unified.DEVELOPING, 8)

    ordered = gs497.ordered_rank_aware_records(
        [halt, dev],
        baseline_order=lambda rows: [dev, halt],
    )

    assert [row["symbol"] for row in ordered] == ["DEV", "HALT"]


def test_installer_wraps_final_sorter_and_is_idempotent(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(gs369, "ordered_escalation_records", baseline)
    gs497.install()
    installed = gs369.ordered_escalation_records

    assert installed is not baseline
    assert getattr(installed, "_gs497_rank_aware_attention_order", False)

    gs497.install()
    assert gs369.ordered_escalation_records is installed


def test_gs497_installs_after_gs495_at_final_render_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    assert "gs497_rank_aware_attention_order" in source
    assert source.index("_install_gs495()") < source.index("_install_gs497()")


def test_scope_lock_is_presentation_order_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
    assert "mission_rank" in source
