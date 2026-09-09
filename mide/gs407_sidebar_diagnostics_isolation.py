"""GS407: isolate sidebar diagnostic controls from the live scan rerun loop.

Live validation on 2026-09-09 showed that interacting with Walter's sidebar
Diagnostics tools can coincide with a full Streamlit app rerun while the live
scheduler is active. That makes a diagnostic interaction capable of starting or
waiting behind a market scan, which is the wrong ownership boundary during live
trading.

GS407 keeps the existing sidebar Diagnostics presentation but moves its three
interactive controls into Streamlit fragments:
* Show removed/pass candidates
* Symbol lookup
* Run Webull Connection Test

Fragment interactions rerun only the diagnostic control itself. They do not request
an app rerun and therefore cannot directly enter Walter's live scan orchestration.
The connection test is additionally disabled while live autoscan or an actual scan
is active so a manual diagnostic client cannot compete with the production scanner.

This module is diagnostics/runtime isolation only. It does not change discovery,
Webull market-data truth, VWAP, SuperTrend, participation, ranking, qualification,
readiness, alerts, autoscan cadence, execution, or orders.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .session_controls import AUTO_SCAN_KEY, SCAN_RUNNING_KEY


SHOW_PASS_LABEL = "Show removed/pass candidates"
SYMBOL_LOOKUP_LABEL = "Symbol lookup"
CONNECTION_TEST_LABEL = "Run Webull Connection Test"

SHOW_PASS_KEY = "_gs407_show_removed_pass"
SYMBOL_LOOKUP_KEY = "_gs407_symbol_lookup"
CONNECTION_BUTTON_KEY = "_gs407_webull_connection_test_button"
CONNECTION_RESULT_KEY = "_gs407_webull_connection_test_result"


def connection_test_allowed(state: Any) -> bool:
    """Return whether the manual diagnostic connection test may run safely."""
    return not bool(state.get(AUTO_SCAN_KEY)) and not bool(state.get(SCAN_RUNNING_KEY))


def _secrets_mapping(st_module) -> dict[str, Any]:
    try:
        return dict(st_module.secrets)
    except Exception:
        return {}


def _run_webull_connection_test_rows(st_module) -> list[dict]:
    """Run the existing explicit Webull diagnostic test outside the app scheduler."""
    from .config import Settings
    from .credentials import WEBULL_CREDENTIAL_NAMES, load_credentials
    from .market_data_providers import AlpacaProvider
    from .webull_connection import run_connection_test
    from .webull_live import WebullOpenAPIClient

    secrets = _secrets_mapping(st_module)
    settings = Settings.from_mapping(secrets)
    credentials = load_credentials(WEBULL_CREDENTIAL_NAMES, secrets=secrets)
    app_key = credentials["WEBULL_APP_KEY"].value
    app_secret = credentials["WEBULL_APP_SECRET"].value
    alpaca_key = str(secrets.get("ALPACA_API_KEY") or "")
    alpaca_secret = str(secrets.get("ALPACA_SECRET_KEY") or "")

    if not app_key or not app_secret:
        raise RuntimeError("Webull credentials are not configured.")
    if not alpaca_key or not alpaca_secret:
        raise RuntimeError("Alpaca credentials are required for the diagnostic symbol master.")

    universe = AlpacaProvider(
        alpaca_key,
        alpaca_secret,
        feed=settings.feed,
        timeout=8,
    ).assets()
    eligible = [
        row.get("symbol")
        for row in universe
        if row.get("tradable", True) and row.get("status", "active") == "active"
    ]
    return run_connection_test(
        app_key=app_key,
        app_secret=app_secret,
        eligible_symbols=eligible,
        client_factory=WebullOpenAPIClient,
    )


def _render_connection_result(st_module, result: dict | None) -> None:
    if not result:
        return
    if result.get("error"):
        st_module.error(str(result["error"]))
        return
    rows = list(result.get("rows") or [])
    if rows:
        st_module.dataframe(rows, use_container_width=True, hide_index=True)
    failures = [row for row in rows if row.get("Status") == "FAIL"]
    (st_module.error if failures else st_module.success)(
        "Webull Connection Test: " + ("FAIL" if failures else "PASS")
    )


def _fragmented_toggle(st_module, original: Callable, label: str, args, kwargs):
    widget_kwargs = dict(kwargs)
    widget_kwargs.setdefault("key", SHOW_PASS_KEY)
    default = bool(widget_kwargs.get("value", False))

    @st_module.fragment
    def render_toggle() -> None:
        original(label, *args, **widget_kwargs)

    render_toggle()
    return bool(st_module.session_state.get(widget_kwargs["key"], default))


def _fragmented_text_input(st_module, original: Callable, label: str, args, kwargs):
    widget_kwargs = dict(kwargs)
    widget_kwargs.setdefault("key", SYMBOL_LOOKUP_KEY)
    default = str(widget_kwargs.get("value", "") or "")

    @st_module.fragment
    def render_text_input() -> None:
        original(label, *args, **widget_kwargs)

    render_text_input()
    return str(st_module.session_state.get(widget_kwargs["key"], default) or "")


def _fragmented_connection_button(st_module, original: Callable, label: str, args, kwargs):
    widget_kwargs = dict(kwargs)
    widget_kwargs.setdefault("key", CONNECTION_BUTTON_KEY)

    @st_module.fragment
    def render_connection_test() -> None:
        allowed = connection_test_allowed(st_module.session_state)
        if not allowed:
            st_module.caption(
                "Connection Test is isolated from live trading. Turn Auto live scan off "
                "before running this manual diagnostic test."
            )
        disabled = bool(widget_kwargs.get("disabled", False)) or not allowed
        button_kwargs = dict(widget_kwargs)
        button_kwargs["disabled"] = disabled
        clicked = original(label, *args, **button_kwargs)
        if clicked and allowed:
            try:
                rows = _run_webull_connection_test_rows(st_module)
                st_module.session_state[CONNECTION_RESULT_KEY] = {
                    "rows": rows,
                    "error": "",
                }
            except Exception as exc:
                st_module.session_state[CONNECTION_RESULT_KEY] = {
                    "rows": [],
                    "error": (
                        "Webull Connection Test failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
        _render_connection_result(
            st_module,
            st_module.session_state.get(CONNECTION_RESULT_KEY),
        )

    render_connection_test()
    # The legacy app-level ``if st.button(...):`` must never execute. The explicit
    # test is owned entirely by the fragment above, outside scan orchestration.
    return False


def install(st_module=None) -> None:
    """Install label-scoped fragment wrappers before app.py renders the sidebar."""
    if st_module is None:
        import streamlit as st_module  # type: ignore[no-redef]

    if not callable(getattr(st_module, "fragment", None)):
        return

    current_toggle = st_module.toggle
    if getattr(current_toggle, "_gs407_sidebar_diagnostics_isolation", False):
        return

    current_text_input = st_module.text_input
    current_button = st_module.button

    @wraps(current_toggle)
    def isolated_toggle(label, *args, **kwargs):
        if str(label) == SHOW_PASS_LABEL:
            return _fragmented_toggle(
                st_module, current_toggle, label, args, kwargs
            )
        return current_toggle(label, *args, **kwargs)

    @wraps(current_text_input)
    def isolated_text_input(label, *args, **kwargs):
        if str(label) == SYMBOL_LOOKUP_LABEL and kwargs.get("placeholder") == "BIYA":
            return _fragmented_text_input(
                st_module, current_text_input, label, args, kwargs
            )
        return current_text_input(label, *args, **kwargs)

    @wraps(current_button)
    def isolated_button(label, *args, **kwargs):
        if str(label) == CONNECTION_TEST_LABEL:
            return _fragmented_connection_button(
                st_module, current_button, label, args, kwargs
            )
        return current_button(label, *args, **kwargs)

    isolated_toggle._gs407_sidebar_diagnostics_isolation = True
    isolated_toggle._gs407_original = current_toggle
    isolated_text_input._gs407_sidebar_diagnostics_isolation = True
    isolated_text_input._gs407_original = current_text_input
    isolated_button._gs407_sidebar_diagnostics_isolation = True
    isolated_button._gs407_original = current_button

    st_module.toggle = isolated_toggle
    st_module.text_input = isolated_text_input
    st_module.button = isolated_button
