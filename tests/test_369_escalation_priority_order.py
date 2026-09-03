from mide import gs310_unified_opportunity_state as unified
from mide import gs363_operator_attention_hierarchy as hierarchy
from mide import ui
from mide.gs369_escalation_priority_order import install, ordered_escalation_records
from mide.startup import ensure_operator_card_order


def _record(symbol: str, state: str, score: int) -> dict:
    record = {
        "symbol": symbol,
        "qualified_for_ranking": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": False,
        "participation_surge_score": 20,
        "expansion_quality": 20,
        "volume_acceleration": 0.5,
        "_test_attention": score,
        "_test_state": state,
    }
    if state == "WATCH FOR ENTRY":
        record.update(
            supertrend_bullish=True,
            participation_surge_score=80,
            expansion_quality=70,
        )
    elif state == "LOOK NOW":
        record["headline"] = "fresh attention catalyst"
    elif state == "DEVELOPING":
        record.update(supertrend_bullish=True, volume_acceleration=1.4)
    elif state == "CHASE / WAIT":
        record.update(supertrend_bullish=True, vwap_distance_pct=8.0)
    return record


def _unordered_records() -> list[dict]:
    return [
        _record("CHASE", "CHASE / WAIT", 99),
        _record("DEV", "DEVELOPING", 80),
        _record("LOOK", "LOOK NOW", 40),
        _record("READY", "WATCH FOR ENTRY", 20),
    ]


def test_opportunity_state_cards_follow_existing_state_priority(monkeypatch):
    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])

    ordered = ordered_escalation_records(_unordered_records())
    assert [record["symbol"] for record in ordered] == ["READY", "LOOK", "DEV", "CHASE"]


def test_sort_uses_current_canonical_state_not_stale_hierarchy_binding(monkeypatch):
    """Live ordering must match the state function that renders the cards."""
    records = [
        _record("CHASE", "CHASE / WAIT", 99),
        _record("DEV", "DEVELOPING", 1),
    ]
    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(
        hierarchy,
        "opportunity_state",
        lambda _record: {"state": unified.CHASE_WAIT},
    )
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["_test_state"]},
    )

    ordered = ordered_escalation_records(records)
    assert [record["symbol"] for record in ordered] == ["DEV", "CHASE"]


def test_install_sorts_before_existing_escalation_renderer(monkeypatch):
    seen = {}

    def original(records):
        seen["symbols"] = [record["symbol"] for record in records]

    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(ui, "render_escalation_engine", original)
    monkeypatch.setattr(ui, "render_walter_mission_control", lambda records: None)
    install()

    ui.render_escalation_engine(
        [
            _record("CHASE", "CHASE / WAIT", 99),
            _record("LOOK", "LOOK NOW", 10),
            _record("DEV", "DEVELOPING", 90),
        ]
    )

    assert seen["symbols"] == ["LOOK", "DEV", "CHASE"]
    assert getattr(ui.render_escalation_engine, "_gs369_escalation_priority_order", False)


def test_install_sorts_actual_gs332_live_mission_route(monkeypatch):
    """The live top Opportunity State stack is routed through mission control."""
    seen = {}

    def live_route(records):
        seen["symbols"] = [record["symbol"] for record in records]

    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(ui, "render_escalation_engine", lambda records: None)
    monkeypatch.setattr(ui, "render_walter_mission_control", live_route)
    install()

    ui.render_walter_mission_control(_unordered_records())

    assert seen["symbols"] == ["READY", "LOOK", "DEV", "CHASE"]
    assert getattr(
        ui.render_walter_mission_control,
        "_gs370_live_opportunity_state_priority_order",
        False,
    )


def test_existing_gs369_escalation_wrapper_does_not_skip_live_route(monkeypatch):
    """Warm installs must still add the live-route sorter independently."""
    seen = {}

    def already_sorted_escalation(records):
        return None

    already_sorted_escalation._gs369_escalation_priority_order = True

    def live_route(records):
        seen["symbols"] = [record["symbol"] for record in records]

    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(ui, "render_escalation_engine", already_sorted_escalation)
    monkeypatch.setattr(ui, "render_walter_mission_control", live_route)
    install()

    ui.render_walter_mission_control(
        [
            _record("CHASE", "CHASE / WAIT", 99),
            _record("DEV", "DEVELOPING", 1),
        ]
    )

    assert seen["symbols"] == ["DEV", "CHASE"]
    assert getattr(
        ui.render_walter_mission_control,
        "_gs370_live_opportunity_state_priority_order",
        False,
    )


def test_startup_guard_wraps_renderer_before_app_can_bind_it(monkeypatch):
    """GS371 closes the exact app-level import-order gap seen in live validation."""
    seen = {}

    def bare_live_route(records):
        seen["symbols"] = [record["symbol"] for record in records]

    monkeypatch.setattr(ui, "hot_list_priority_score", lambda record: record["_test_attention"])
    monkeypatch.setattr(ui, "render_escalation_engine", lambda records: None)
    monkeypatch.setattr(ui, "render_walter_mission_control", bare_live_route)

    ensure_operator_card_order()
    app_bound_renderer = ui.render_walter_mission_control
    app_bound_renderer(
        [
            _record("CHASE", "CHASE / WAIT", 99),
            _record("DEV", "DEVELOPING", 1),
        ]
    )

    assert seen["symbols"] == ["DEV", "CHASE"]
    assert getattr(
        app_bound_renderer,
        "_gs370_live_opportunity_state_priority_order",
        False,
    )
