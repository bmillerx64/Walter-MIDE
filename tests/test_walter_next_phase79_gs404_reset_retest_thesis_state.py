"""Phase 79: GS404 reset/retest LOOK NOW meaning belongs to Thesis / State."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs404_reset_retest_look_now as gs404
from mide.authorities import market_evidence
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def _base(state=thesis_state.DEVELOPING):
    return {
        "state": state,
        "color": thesis_state.STATE_COLORS[state],
        "reason": "base",
        "next_step": "base next",
    }


def _evidence(recent=True):
    return {
        "recent": recent,
        "trigger": (
            "RESET_RETEST_NEAR_VWAP"
            if recent
            else None
        ),
        "chart_review_only": True,
        "entry_authority_unchanged": True,
    }


def test_phase79_authority_promotes_reset_retest_to_look_now(monkeypatch):
    monkeypatch.setattr(
        market_evidence,
        "reset_retest_attention_evidence",
        lambda _record: _evidence(True),
    )

    view = thesis_state.reset_retest_opportunity_state(
        lambda _record: _base(),
        {"symbol": "ZTG"},
    )

    assert view["state"] == thesis_state.LOOK_NOW
    assert view["color"] == thesis_state.STATE_COLORS[thesis_state.LOOK_NOW]
    assert gs404.RESET_RETEST_PROVENANCE in view["attention_provenance"]
    assert view["reset_retest_attention"]["chart_review_only"] is True
    assert "investigation only" in view["next_step"].lower()


def test_phase79_authority_never_downgrades_stronger_or_halted_state(monkeypatch):
    monkeypatch.setattr(
        market_evidence,
        "reset_retest_attention_evidence",
        lambda _record: _evidence(True),
    )
    for state in (
        thesis_state.WATCH_FOR_ENTRY,
        thesis_state.HALTED,
    ):
        view = thesis_state.reset_retest_opportunity_state(
            lambda _record, state=state: _base(state),
            {"symbol": "ZTG"},
        )
        assert view["state"] == state


def test_phase79_authority_leaves_nonrecent_state_unchanged(monkeypatch):
    monkeypatch.setattr(
        market_evidence,
        "reset_retest_attention_evidence",
        lambda _record: _evidence(False),
    )
    view = thesis_state.reset_retest_opportunity_state(
        lambda _record: _base(),
        {"symbol": "ZTG"},
    )
    assert view == _base()


def test_phase79_legacy_state_name_delegates_lazily(monkeypatch):
    sentinel = {
        "state": "AUTHORITY",
        "color": "x",
    }
    monkeypatch.setattr(
        thesis_state,
        "reset_retest_opportunity_state",
        lambda _original, _record: dict(sentinel),
    )
    result = gs404.reset_retest_opportunity_state(
        {},
        lambda _record: _base(),
    )
    assert result == sentinel


def test_phase79_stale_thesis_generation_preserves_local_fallback(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "_thesis_state",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs404,
        "reset_retest_attention_evidence",
        lambda _record: _evidence(True),
    )

    result = gs404.reset_retest_opportunity_state(
        {},
        lambda _record: _base(),
    )
    assert result["state"] == thesis_state.LOOK_NOW
    assert gs404.RESET_RETEST_PROVENANCE in result["attention_provenance"]


def test_phase79_presentation_injection_and_runtime_bind_remain_for_later_slice():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    assert "def augment_reset_retest_records(" in legacy
    assert "def install(" in legacy
    assert "_gs404_reset_retest" in legacy


def test_phase79_state_meaning_lives_in_thesis_state():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")

    assert "def reset_retest_opportunity_state(" in authority
    assert '"reset_retest_opportunity_state"' in legacy


def test_phase79_scope_is_thesis_state_only():
    source = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS404 reset/retest LOOK NOW state meaning")
    end = source.index('_LEADER_RESET_PROVENANCE =', start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        "actionable_candidate_records =",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
