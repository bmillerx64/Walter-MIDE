"""Thin, mockable boundary around the official Webull OpenAPI Python SDK."""

from __future__ import annotations

import importlib
import json
import logging
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


HTTP_HOST = "https://api.webull.com"
STREAM_HOST = "data-api.webull.com"
SNAPSHOT_OPERATION = "GET /openapi/market-data/stock/snapshot"
MAX_SNAPSHOT_SYMBOLS = 100
LOGGER = logging.getLogger(__name__)
_SECRET_HEADER_PARTS = ("authorization", "signature", "secret", "token", "cookie", "app-key")


def _safe_headers(headers) -> dict:
    """Return headers suitable for diagnostics without credential material."""
    return {str(key): ("<redacted>" if any(part in str(key).lower()
            for part in _SECRET_HEADER_PARTS) else str(value))
            for key, value in dict(headers or {}).items()}


def _body_text(value) -> str:
    if value is None:
        return "<empty>"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return repr(value)


def _exact_url(url: str, kwargs: dict) -> str:
    """Render query parameters supplied separately by requests-style clients."""
    params = kwargs.get("params")
    if not params:
        return str(url)
    parts = urlsplit(str(url))
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.extend(params.items() if hasattr(params, "items") else params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))


class TracedHTTPTransport:
    """Transparent SDK transport proxy that records complete, redacted exchanges."""

    def __init__(self, transport):
        object.__setattr__(self, "_transport", transport)

    def __getattr__(self, name):
        return getattr(self._transport, name)

    def __setattr__(self, name, value):
        setattr(self._transport, name, value)

    def request(self, method, url, *args, **kwargs):
        logged_url = _exact_url(url, kwargs)
        headers = kwargs.get("headers") or {}
        body = kwargs.get("body", kwargs.get("data", kwargs.get("json")))
        LOGGER.info("WEBULL HTTP request method=%s url=%s headers=%s body=%s",
                    method, logged_url, _safe_headers(headers), _body_text(body))
        try:
            response = self._transport.request(method, url, *args, **kwargs)
        except Exception:
            LOGGER.exception("WEBULL HTTP request failed method=%s url=%s", method, logged_url)
            raise
        status = getattr(response, "status", getattr(response, "status_code", "<unknown>"))
        response_headers = getattr(response, "headers", {})
        response_body = getattr(response, "data", None)
        if response_body is None:
            response_body = getattr(response, "text", None)
        LOGGER.info("WEBULL HTTP response method=%s url=%s status=%s headers=%s body=%s",
                    method, logged_url, status, _safe_headers(response_headers), _body_text(response_body))
        return response


def _install_http_trace(sdk_client) -> bool:
    """Instrument the official SDK's requests/urllib3 transport when exposed."""
    candidates = [sdk_client]
    for name in ("api_client", "rest_client"):
        value = getattr(sdk_client, name, None)
        if value is not None:
            candidates.append(value)
            nested = getattr(value, "rest_client", None)
            if nested is not None:
                candidates.append(nested)
    for owner in candidates:
        for name in ("session", "pool_manager"):
            transport = getattr(owner, name, None)
            if transport is not None and callable(getattr(transport, "request", None)):
                if not isinstance(transport, TracedHTTPTransport):
                    setattr(owner, name, TracedHTTPTransport(transport))
                return True
    LOGGER.warning("WEBULL HTTP tracing unavailable: official SDK exposes no supported transport")
    return False


def create_official_client(app_key: str, app_secret: str):
    """Construct the SDK's published data clients without package discovery."""
    try:
        core_module = importlib.import_module("webull.core.client")
        data_module = importlib.import_module("webull.data.data_client")
        streaming_module = importlib.import_module(
            "webull.data.data_streaming_client"
        )
    except ImportError as exc:
        raise RuntimeError(
            "Required Webull SDK package is not installed: "
            "webull-openapi-python-sdk"
        ) from exc

    api_client = core_module.ApiClient(app_key=app_key, app_secret=app_secret)
    data_client = data_module.DataClient(api_client)
    # Keep the two public SDK clients together at the adapter boundary.  The
    # streaming client is lazy so snapshot-only runs never open streaming
    # resources merely by constructing the REST client.
    data_client._walter_streaming_client_factory = lambda: (
        streaming_module.DataStreamingClient(api_client)
    )
    LOGGER.info(
        "WEBULL SDK initialization complete using %s.DataClient and %s.DataStreamingClient",
        data_module.__name__, streaming_module.__name__,
    )
    return data_client


def _plain(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


class WebullSDKClient:
    """Walter-shaped adapter; signing, HTTP, and MQTT remain SDK duties."""

    base_url = HTTP_HOST
    snapshot_path = "/openapi/market-data/stock/snapshot"
    stream_host = STREAM_HOST

    def __init__(self, app_key: str, app_secret: str, *, sdk_client=None):
        LOGGER.info("WEBULL SDK adapter initialization started injected_client=%s",
                    sdk_client is not None)
        self.sdk_client = sdk_client or create_official_client(app_key, app_secret)
        self.http_trace_installed = _install_http_trace(self.sdk_client)
        LOGGER.info("WEBULL SDK adapter initialization complete http_trace_installed=%s",
                    self.http_trace_installed)

    def _operation(self, names: tuple[str, ...]):
        objects = (self.sdk_client,
                   getattr(self.sdk_client, "market_data", None),
                   getattr(self.sdk_client, "market_data_api", None))
        for obj in objects:
            for name in names:
                method = getattr(obj, name, None) if obj is not None else None
                if callable(method):
                    return method
        raise RuntimeError("Webull OpenAPI SDK lacks operation: " + "/".join(names))

    def stock_snapshot(self, symbols: Iterable[str]):
        symbols = list(symbols)
        if len(symbols) > MAX_SNAPSHOT_SYMBOLS:
            raise ValueError("Webull snapshot requests are limited to 100 symbols")
        # ``get_stock_snapshot`` remains accepted solely at the injected-test
        # boundary; installed SDK clients use their published ``get_snapshot``.
        method = self._operation(("get_snapshot", "get_stock_snapshot"))
        arguments = dict(symbols=",".join(symbols), category="US_STOCK",
                         extend_hour_required=True, overnight_required=True)
        try:
            return _plain(method(**arguments))
        except TypeError:
            # Some generated SDK versions name the overnight option explicitly
            # as include_overnight; neither fallback constructs an HTTP request.
            arguments.pop("overnight_required")
            arguments["include_overnight"] = True
            return _plain(method(**arguments))

    def bars(self, **arguments):
        method = self._operation(("get_history_bar",))
        return _plain(method(**arguments))

    def stream(self, callback):
        factory = getattr(self.sdk_client, "_walter_streaming_client_factory", None)
        if factory is None:
            raise RuntimeError("Webull OpenAPI SDK lacks DataStreamingClient")
        client = factory()
        client.callback = callback
        return client
