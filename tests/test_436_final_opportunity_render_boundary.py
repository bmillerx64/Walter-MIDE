from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs414_final_enriched_opportunity_order as final_order
from mide import ui


def _record(symbol: str, state: str) -> dict:
    return {
        "symbol": symbol,
        "forced_state": state,
        "qualified_for_ranking": True,
        "price": 1.0,
    }


def _force_state(monkeypatch) -> None:
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["forced_state"]},
    )
    monkeypatch.setattr(final_order, "_install_gs419", lambda: None)


def test_inherited_gs414_marker_cannot_suppress_final_rebind(monkeypatch):
    """A copied compatibility marker is not proof that GS414 owns the outer call."""
    _force_state(monkeypatch)
    enriched = [
        _record("CHASE", unified.CHASE_WAIT),
        _record("DEV", unified.DEVELOPING),
        _record("LOOK", unified.LOOK_NOW),
        _record("READY", unified.WATCH_FOR_ENTRY),
    ]
    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        lambda _records: list(enriched),
    )

    rendered = []

    def stale_outer_renderer(records):
        # Reproduce the nested GS310 collection read that can otherwise undo an
        # earlier outer sort after awareness/reclaim enrichment.
        nested = ui.actionable_candidate_records(records)[:5]
        rendered.extend(record["symbol"] for record in nested)

    # This is the live warm-runtime failure: a later wrapper inherited the historical
    # marker even though the actual GS414 freeze is no longer the outer boundary.
    stale_outer_renderer._gs414_final_enriched_opportunity_order = True
    monkeypatch.setattr(ui, "render_escalation_engine", stale_outer_renderer)

    final_order.install()
    rebound = ui.render_escalation_engine

    assert rebound is not stale_outer_renderer
    assert getattr(rebound, final_order.FINAL_ORDER_OWNER_ATTR, False) is True

    rebound([_record("CHASE", unified.CHASE_WAIT)])
    assert rendered == ["READY", "LOOK", "DEV", "CHASE"]


def test_actual_owner_sentinel_makes_reinstall_idempotent(monkeypatch):
    _force_state(monkeypatch)
    monkeypatch.setattr(ui, "actionable_candidate_records", lambda records: list(records))
    monkeypatch.setattr(ui, "render_escalation_engine", lambda _records: None)

    final_order.install()
    first = ui.render_escalation_engine
    final_order.install()

    assert ui.render_escalation_engine is first
    assert getattr(first, final_order.FINAL_ORDER_OWNER_ATTR, False) is True
    assert not final_order.FINAL_ORDER_OWNER_ATTR.startswith("_gs")


def test_gs436_reasserts_final_order_after_all_late_runtime_installers():
    source = Path("mide/startup.py").read_text(encoding="utf-8")

    assert "gs414_final_enriched_opportunity_order" in source
    assert source.index("install_gs435()") < source.rindex("install_final_order()")


def test_gs436_deployment_marker_changes_no_dependency_pins():
    source = Path("requirements.txt").read_text(encoding="utf-8")
    pins = [line for line in source.splitlines() if line and not line.startswith("#")]

    assert "GS436 deployment marker" in source
    assert pins == [
        "streamlit==1.62.0",
        "pandas==2.3.3",
        "numpy==2.5.1",
        "requests==2.34.2",
        "paho-mqtt==1.6.1",
        "webull-openapi-python-sdk==2.0.16",
    ]
