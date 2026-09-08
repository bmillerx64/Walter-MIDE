from mide import gs367_browser_audio_broker as broker
from mide import gs392_operator_order_audio as gs392
from mide import ui


def _record(symbol: str, state: str) -> dict:
    if state == "WATCH FOR ENTRY":
        return {
            "symbol": symbol,
            "vwap_relation": "above",
            "vwap_distance_pct": 1.0,
            "supertrend_bullish": True,
            "participation_surge_score": 90.0,
            "participation_gate": {"passed": True},
            "expansion_quality": 80.0,
        }
    if state == "LOOK NOW":
        return {
            "symbol": symbol,
            "vwap_relation": "above",
            "vwap_distance_pct": 1.0,
            "supertrend_bullish": False,
            "headline": "fresh catalyst",
            "participation_surge_score": 20.0,
            "expansion_quality": 20.0,
        }
    if state == "DEVELOPING":
        return {
            "symbol": symbol,
            "vwap_relation": "above",
            "vwap_distance_pct": 1.0,
            "supertrend_bullish": True,
            "volume_acceleration": 1.5,
            "participation_surge_score": 20.0,
            "expansion_quality": 20.0,
        }
    if state == "CHASE / WAIT":
        return {
            "symbol": symbol,
            "vwap_relation": "above",
            "vwap_distance_pct": 4.0,
            "supertrend_bullish": True,
            "participation_surge_score": 90.0,
            "expansion_quality": 80.0,
        }
    raise AssertionError(state)


def test_gs392_rewraps_renderer_even_when_old_order_marker_was_inherited(monkeypatch):
    seen = {}

    def stale_renderer(records):
        seen["symbols"] = [record["symbol"] for record in records]

    # Reproduce the live failure mode: a later wrapper inherited GS369's marker,
    # so GS369's installer would incorrectly assume ordering was still outermost.
    stale_renderer._gs369_escalation_priority_order = True
    monkeypatch.setattr(ui, "render_escalation_engine", stale_renderer)

    gs392.install()
    ui.render_escalation_engine(
        [
            _record("CHASE", "CHASE / WAIT"),
            _record("DEV", "DEVELOPING"),
            _record("LOOK", "LOOK NOW"),
            _record("WATCH", "WATCH FOR ENTRY"),
        ]
    )

    assert seen["symbols"] == ["WATCH", "LOOK", "DEV", "CHASE"]
    assert getattr(ui.render_escalation_engine, "_gs392_final_operator_order", False)


def test_gs392_audio_patterns_are_acoustically_distinct():
    gs392.install()

    routine = broker.tone_pattern(1)
    look_now = broker.tone_pattern(2)
    watch = broker.tone_pattern(3)

    assert routine == gs392.ROUTINE_PATTERN
    assert look_now == gs392.LOOK_NOW_PATTERN
    assert watch == gs392.WATCH_FOR_ENTRY_PATTERN
    assert len(routine) == 1
    assert len(look_now) == 2
    assert len(watch) == 3
    assert routine[0][0] != look_now[0][0]
    assert look_now[1][0] - look_now[0][0] >= 500
    assert look_now[1][1] - look_now[0][1] >= 0.25
    assert watch[-1][0] > watch[0][0]


def test_gs392_browser_markup_serializes_new_look_now_pattern():
    gs392.install()
    markup = broker.browser_broker_markup("scan-gs392", 2)

    assert "900" in markup
    assert "1480" in markup
    assert "0.28" in markup
