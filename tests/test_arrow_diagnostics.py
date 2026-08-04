import logging

import pandas as pd

from mide.arrow_diagnostics import arrow_violations, instrument_streamlit_tables


def test_diagnostic_identifies_column_values_and_python_types():
    frame = pd.DataFrame({"safe": [1, 2], "Actual Value": [1.5, "+4.00%"]})

    violations = arrow_violations(frame, dataframe_name="rejected candidates")

    assert len(violations) == 1
    assert violations[0]["dataframe"] == "rejected candidates"
    assert violations[0]["column"] == "Actual Value"
    assert violations[0]["python_types"] == ["float", "str"]
    assert violations[0]["values"] == [
        {"index": 0, "value": "1.5", "python_type": "float"},
        {"index": 1, "value": "'+4.00%'", "python_type": "str"},
    ]


def test_streamlit_instrumentation_preserves_value_and_logs_failure(caplog):
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
    frame = pd.DataFrame({"mixed": [2.0, "unknown"]})
    instrument_streamlit_tables(streamlit)

    with caplog.at_level(logging.ERROR):
        result = streamlit.dataframe(frame, hide_index=True)

    assert result == "rendered"
    assert streamlit.received is frame
    assert "ARROW_SERIALIZATION_VIOLATION" in caplog.text
    assert "'column': 'mixed'" in caplog.text
