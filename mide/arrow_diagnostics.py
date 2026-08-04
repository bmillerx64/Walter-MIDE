"""Read-only diagnostics for values that pandas cannot serialize to Arrow."""

from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any

import pandas as pd
import pyarrow as pa


LOGGER = logging.getLogger(__name__)


def _is_missing(value: Any) -> bool:
    """Return pandas missingness only when it is an unambiguous scalar result."""
    missing = pd.isna(value)
    try:
        return bool(missing)
    except (TypeError, ValueError):
        return False


def arrow_violations(value: Any, *, dataframe_name: str) -> list[dict[str, Any]]:
    """Return the columns and Python values that fail Arrow conversion.

    The input is copied into a DataFrame only for inspection.  No coercion or
    replacement is performed, so this diagnostic cannot mask the Streamlit
    serialization error under investigation.
    """
    frame = value if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
    try:
        pa.Table.from_pandas(frame)
    except (pa.ArrowInvalid, pa.ArrowTypeError):
        pass
    else:
        return []

    violations = []
    for column in frame.columns:
        series = frame[column]
        try:
            pa.Table.from_pandas(series.to_frame())
        except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
            typed_values = [
                {"index": index, "value": repr(item), "python_type": type(item).__name__}
                for index, item in series.items()
                if not _is_missing(item)
            ]
            violations.append(
                {
                    "dataframe": dataframe_name,
                    "column": str(column),
                    "pandas_dtype": str(series.dtype),
                    "python_types": sorted({item["python_type"] for item in typed_values}),
                    "values": typed_values,
                    "arrow_error": str(exc),
                }
            )
    return violations


def log_arrow_violations(value: Any, *, dataframe_name: str) -> list[dict[str, Any]]:
    """Log an exact, machine-readable description of non-Arrow columns."""
    violations = arrow_violations(value, dataframe_name=dataframe_name)
    for violation in violations:
        LOGGER.error("ARROW_SERIALIZATION_VIOLATION %r", violation)
    return violations


def instrument_streamlit_tables(streamlit_module: Any) -> None:
    """Inspect every top-level Streamlit table call without changing its input."""
    for method_name in ("dataframe", "table"):
        original = getattr(streamlit_module, method_name)
        if getattr(original, "_walter_arrow_diagnostic", False):
            continue

        @wraps(original)
        def inspected(value=None, *args, _original=original, _name=method_name, **kwargs):
            caller = inspect.currentframe().f_back
            location = f"{caller.f_code.co_filename}:{caller.f_lineno}"
            log_arrow_violations(value, dataframe_name=f"st.{_name} at {location}")
            return _original(value, *args, **kwargs)

        inspected._walter_arrow_diagnostic = True
        setattr(streamlit_module, method_name, inspected)


def inspect_session_state_dataframes(session_state: Any) -> list[dict[str, Any]]:
    """Inspect DataFrames directly retained in session state, without mutation."""
    violations = []
    for key in session_state:
        value = session_state[key]
        if isinstance(value, pd.DataFrame):
            violations.extend(
                log_arrow_violations(value, dataframe_name=f"st.session_state[{key!r}]")
            )
    return violations
