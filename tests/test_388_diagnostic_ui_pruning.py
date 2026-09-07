from __future__ import annotations

from mide.arrow_diagnostics import instrument_streamlit_tables
from mide import gs388_diagnostic_ui_pruning as gs388
from mide.flight_recorder import FlightRecorder


def test_nested_diagnostic_cells_render_as_json_instead_of_object_object():
    class Streamlit:
        def __init__(self):
            self.received = None

        def dataframe(self, value, **_kwargs):
            self.received = value
            return "rendered"

        def table(self, value, **_kwargs):
            self.received = value
            return "rendered"

    streamlit = Streamlit()
    rows = [
        {
            "symbol": "TEST",
            "decision_booleans": [
                {
                    "boolean": "VWAP",
                    "passed": False,
                    "metric_values": {"vwap_distance_pct": -3.2},
                }
            ],
        }
    ]

    instrument_streamlit_tables(streamlit)
    assert streamlit.dataframe(rows) == "rendered"

    rendered = streamlit.received.loc[0, "decision_booleans"]
    assert isinstance(rendered, str)
    assert '"boolean": "VWAP"' in rendered
    assert '"vwap_distance_pct": -3.2' in rendered
    assert "[object Object]" not in rendered
    assert isinstance(rows[0]["decision_booleans"], list)


def test_latest_scan_display_alias_uses_authoritative_participation_prefilter_count():
    source = {
        "scan_id": "scan-1",
        "funnel": {
            "Sampled": 55,
            "Participation Prefiltered": 18,
            "Analyzed": 18,
        },
    }

    displayed = gs388.display_safe_latest_scan(source)

    assert displayed["funnel"]["Prefiltered"] == 18
    assert displayed["funnel"]["Participation Prefiltered"] == 18
    assert "Prefiltered" not in source["funnel"]


def test_latest_scan_display_alias_never_overwrites_explicit_value():
    source = {
        "funnel": {
            "Participation Prefiltered": 18,
            "Prefiltered": 17,
        }
    }

    displayed = gs388.display_safe_latest_scan(source)

    assert displayed["funnel"]["Prefiltered"] == 17


def test_gs388_latest_scan_wrapper_is_installed():
    assert getattr(
        FlightRecorder.latest_scan,
        "_gs388_diagnostic_ui_pruning",
        False,
    ) is True
