from mide import gs310_unified_opportunity_state as unified
from mide import ui
from mide.gs401_final_opportunity_order import final_visible_records, install


def _record(symbol: str, state: str) -> dict:
    return {
        "symbol": symbol,
        "forced_state": state,
        "qualified_for_ranking": True,
        "price": 1.0,
    }


def test_gs401_sorts_after_actionable_awareness_enrichment(monkeypatch):
    enriched = [
        _record("CHASE", unified.CHASE_WAIT),
        _record("DEV", unified.DEVELOPING),
        _record("LOOK", unified.LOOK_NOW),
        _record("READY", unified.WATCH_FOR_ENTRY),
    ]

    # Reproduce the live failure: a later actionable/awareness layer returns a
    # different order than the already-sorted outer renderer input.
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda _records: list(enriched))
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["forced_state"]},
    )

    visible = final_visible_records(list(reversed(enriched)))
    assert [record["symbol"] for record in visible] == [
        "READY",
        "LOOK",
        "DEV",
        "CHASE",
    ]


def test_gs401_limits_only_after_final_priority_sort(monkeypatch):
    enriched = [
        _record("CHASE1", unified.CHASE_WAIT),
        _record("CHASE2", unified.CHASE_WAIT),
        _record("CHASE3", unified.CHASE_WAIT),
        _record("CHASE4", unified.CHASE_WAIT),
        _record("CHASE5", unified.CHASE_WAIT),
        _record("DEV", unified.DEVELOPING),
    ]
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda _records: list(enriched))
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["forced_state"]},
    )

    visible = final_visible_records(enriched)
    assert visible[0]["symbol"] == "DEV"
    assert len(visible) == 5
    assert "CHASE5" not in {record["symbol"] for record in visible}


def test_gs401_install_is_idempotent(monkeypatch):
    original = ui.render_escalation_engine
    monkeypatch.setattr(ui, "render_escalation_engine", original)

    install()
    first = ui.render_escalation_engine
    install()

    assert ui.render_escalation_engine is first
    assert getattr(first, "_gs401_final_opportunity_order", False)
