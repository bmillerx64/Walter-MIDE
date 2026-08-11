"""Diagnostics for Arrow-backed Streamlit tables."""
from __future__ import annotations
import inspect
import json
import logging
from functools import wraps
from typing import Any
import pandas as pd
import pyarrow as pa

LOGGER = logging.getLogger(__name__)

def _is_missing(value: Any) -> bool:
    missing = pd.isna(value)
    try: return bool(missing)
    except (TypeError, ValueError): return False

def arrow_violations(value: Any, *, dataframe_name: str) -> list[dict[str, Any]]:
    frame = value if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
    try: pa.Table.from_pandas(frame)
    except (pa.ArrowInvalid, pa.ArrowTypeError): pass
    else: return []
    violations = []
    for column in frame.columns:
        series = frame[column]
        try: pa.Table.from_pandas(series.to_frame())
        except (pa.ArrowInvalid, pa.ArrowTypeError) as exc:
            typed_values = [{"index": index, "value": repr(item), "python_type": type(item).__name__}
                            for index, item in series.items() if not _is_missing(item)]
            violations.append({"dataframe": dataframe_name, "column": str(column),
                               "pandas_dtype": str(series.dtype),
                               "python_types": sorted({item["python_type"] for item in typed_values}),
                               "values": typed_values, "arrow_error": str(exc)})
    return violations

def log_arrow_violations(value: Any, *, dataframe_name: str) -> list[dict[str, Any]]:
    violations = arrow_violations(value, dataframe_name=dataframe_name)
    for violation in violations:
        LOGGER.error("ARROW_SERIALIZATION_VIOLATION %r", violation)
    return violations

def _arrow_safe_table_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=str)
    return value

def _arrow_safe_frame(value: Any, violating_columns: set[str]) -> pd.DataFrame:
    frame = value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame(value)
    for column in frame.columns:
        if str(column) in violating_columns:
            frame[column] = frame[column].map(_arrow_safe_table_value)
    return frame

def instrument_streamlit_tables(streamlit_module: Any) -> None:
    """Log serialization problems without mutating the value handed to Streamlit."""
    for method_name in ("dataframe", "table"):
        original = getattr(streamlit_module, method_name)
        if getattr(original, "_walter_arrow_diagnostic", False): continue
        @wraps(original)
        def inspected(value=None, *args, _original=original, _name=method_name, **kwargs):
            caller = inspect.currentframe().f_back
            location = f"{caller.f_code.co_filename}:{caller.f_lineno}"
            log_arrow_violations(value, dataframe_name=f"st.{_name} at {location}")
            return _original(value, *args, **kwargs)
        inspected._walter_arrow_diagnostic = True
        setattr(streamlit_module, method_name, inspected)

def inspect_session_state_dataframes(session_state: Any) -> list[dict[str, Any]]:
    violations = []
    for key in session_state:
        value = session_state[key]
        if isinstance(value, pd.DataFrame):
            violations.extend(log_arrow_violations(value, dataframe_name=f"st.session_state[{key!r}]"))
    return violations
