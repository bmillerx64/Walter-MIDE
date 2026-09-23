from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs369_escalation_priority_order as gs369
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide import gs517_fresh_event_priority as gs517


def _record(symbol, state, rank=None, *, fresh=False):
    row = {"symbol": symbol, "_state": state, "_fresh": fresh}
    if rank is not None:
        row["mission_rank"] = rank
        row["terminal_stage"] = "Mission Ranking and Publication"
        row["terminal_outcome"] = "Qualified and Ranked"
    return row


def _patch_runtime(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["_state"], "reason": "test"},
    )
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: {
            "active": bool(record.get("_fresh")),
            "new_rung": "1m" if record.get("_fresh") else None,
        },
    )


def test_sept21_xtia_fresh_maturation_beats_static_sdst_rank(monkeypatch):
    _patch_runtime(monkeypatch)
    sdst = _record("SDST", unified.LOOK_NOW, 2, fresh=False)
    xtia = _record("XTIA", unified.LOOK_NOW, 8, fresh=True)

    # Model GS497's incoming rank-first order exactly: SDST before XTIA.
    ordered = gs517.ordered_fresh_event_records(
        [sdst, xtia],
        baseline_order=lambda rows: [sdst, xtia],
    )

    assert [row["symbol"] for row in ordered] == ["XTIA", "SDST"]


def test_fresh_extended_maturation_keeps_anti_chase_state_but_wins_attention(monkeypatch):
    _patch_runtime(monkeypatch)
    generic = _record("STATIC", unified.LOOK_NOW, 1, fresh=False)
    mover = _record("MOVER", unified.CHASE_WAIT, 7, fresh=True)

    ordered = gs517.ordered_fresh_event_records(
        [generic, mover],
        baseline_order=lambda rows: [generic, mover],
    )

    assert [row["symbol"] for row in ordered] == ["MOVER", "STATIC"]
    assert unified.opportunity_state(ordered[0])["state"] == unified.CHASE_WAIT


def test_nonfresh_records_preserve_gs497_order_exactly(monkeypatch):
    _patch_runtime(monkeypatch)
    rank_one = _record("ONE", unified.CHASE_WAIT, 1, fresh=False)
    rank_two = _record("TWO", unified.LOOK_NOW, 2, fresh=False)
    baseline = [rank_one, rank_two]

    ordered = gs517.ordered_fresh_event_records(
        list(reversed(baseline)),
        baseline_order=lambda rows: list(baseline),
    )

    assert ordered == baseline


def test_watch_for_entry_first_and_halted_last(monkeypatch):
    _patch_runtime(monkeypatch)
    ready = _record("READY", unified.WATCH_FOR_ENTRY, 9, fresh=False)
    mover = _record("MOVER", unified.CHASE_WAIT, 7, fresh=True)
    halt = _record("HALT", unified.HALTED, 1, fresh=True)

    ordered = gs517.ordered_fresh_event_records(
        [halt, mover, ready],
        baseline_order=lambda rows: [ready, halt, mover],
    )

    assert [row["symbol"] for row in ordered] == ["READY", "MOVER", "HALT"]


def test_installer_wraps_gs497_order_and_is_idempotent(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(gs369, "ordered_escalation_records", baseline)
    gs517.install()
    installed = gs369.ordered_escalation_records

    assert installed is not baseline
    assert getattr(installed, "_gs517_fresh_event_priority", False)

    gs517.install()
    assert gs369.ordered_escalation_records is installed


def test_gs517_installs_after_gs497_at_final_render_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    assert "gs517_fresh_event_priority" in source
    assert source.index("_install_gs497()") < source.index("_install_gs517()")


def test_scope_lock_is_presentation_order_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    source = authority.split(
        "# Authoritative operator ordering", 1
    )[1].split("# Base extraordinary-mover presentation", 1)[0]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
    assert "progression_signal" in source
