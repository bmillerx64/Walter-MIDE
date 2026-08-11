"""Thin, mockable boundary around the official Webull OpenAPI Python SDK."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
import json
import logging
from pathlib import Path
import re
from threading import Lock
import time
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo


HTTP_HOST = "https://api.webull.com"
STREAM_HOST = "data-api.webull.com"
SNAPSHOT_OPERATION = "GET /openapi/market-data/stock/snapshot"
MAX_SNAPSHOT_SYMBOLS = 100
LOGGER = logging.getLogger(__name__)
_SECRET_HEADER_PARTS = ("authorization", "signature", "secret", "token", "cookie", "app-key")
_HISTORY_BAR_RATE_LOCK = Lock()
_HISTORY_BAR_LAST_CALL = 0.0
_HISTORY_BAR_MIN_INTERVAL_SECONDS = 1.05


def _suppress_official_sdk_logging() -> None:
    """Silence SDK-owned loggers that emit raw signed requests and tokens."""
    prefixes = ("webull.core", "webull.data")
    names = set(prefixes)
    names.update(name for name in logging.Logger.manager.loggerDict
                 if name.startswith(prefixes))
    for name in names:
        sdk_logger = logging.getLogger(name)
        sdk_logger.disabled = True
        sdk_logger.handlers.clear()


def _safe_headers(headers) -> dict:
    """Return headers suitable for diagnostics without credential material."""
    return {str(key): ("<redacted>" if _secret_key(key) else str(value))
            for key, value in dict(headers or {}).items()}


def _secret_key(key: object) -> bool:
    normalized = str(key).lower().replace("_", "-")
    return any(part in normalized for part in _SECRET_HEADER_PARTS) or normalized == "nonce"


def _safe_value(value):
    if isinstance(value, dict):
        return {str(key): ("<redacted>" if _secret_key(key) else _safe_value(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return value


_SECRET_TEXT_VALUE = re.compile(
    r"(?i)([\"']?(?:authorization|signature|[^\s\"']*(?:secret|token|nonce|app[_-]?key))"
    r"[\"']?\s*[:=]\s*)([\"']?)[^\s,;}\"']+\2"
)


def _redact_text(value: str) -> str:
    return _SECRET_TEXT_VALUE.sub(r"\1<redacted>", value)


def _body_text(value) -> str:
    if value is None:
        return "<empty>"
    if isinstance(value, bytes):
        return _redact_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, str):
        return _redact_text(value)
    try:
        return json.dumps(_safe_value(value), sort_keys=True, default=str)
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
    query = [(key, "<redacted>" if _secret_key(key) else value) for key, value in query]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment))


def _wait_for_history_bar_slot() -> None:
    """Respect Webull's published one-call-per-second history-bar limit."""
    global _HISTORY_BAR_LAST_CALL
    with _HISTORY_BAR_RATE_LOCK:
        now = time.monotonic()
        delay = _HISTORY_BAR_MIN_INTERVAL_SECONDS - (now - _HISTORY_BAR_LAST_CALL)
        if delay > 0:
            time.sleep(delay)
        _HISTORY_BAR_LAST_CALL = time.monotonic()


def _invalid_history_symbol(exc: Exception) -> bool:
    message = f"{type(exc).__name__}: {exc}".upper()
    return "INVALID_SYMBOL" in message or ("417" in message and "SYMBOL" in message)


def _clamp_future_session_start(parsed: datetime, *, now: datetime | None = None) -> datetime:
    """Move an impossible future intraday start to the latest prior U.S. weekday.

    Walter anchors current-session history at 04:00 America/New_York. Between
    midnight and 04:00 ET that anchor is still in the future, so Webull correctly
    returns an empty current-session batch. Preserve the intended prior market
    session instead of sending an impossible start time. Historical-profile calls
    carry an explicit end_time and therefore do not use this correction.
    """
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if parsed <= now:
        return parsed

    eastern = ZoneInfo("America/New_York")
    candidate = parsed.astimezone(eastern) - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.astimezone(parsed.tzinfo)


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

    _suppress_official_sdk_logging()

    api_client = core_module.ApiClient(app_key=app_key, app_secret=app_secret, region_id="us")
    data_client = data_module.DataClient(api_client)
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
        value = value.to_dict()
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    json_method = getattr(value, "json", None)
    if callable(json_method):
        value = json_method()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {_plain(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_plain(item) for item in value)
    return value


class WebullSDKClient:
    """Walter-shaped adapter; signing, HTTP, and MQTT remain SDK duties."""

    base_url = HTTP_HOST
    snapshot_path = "/openapi/market-data/stock/snapshot"
    stream_host = STREAM_HOST

    def __init__(self, app_key: str, app_secret: str, *, sdk_client=None):
        LOGGER.info("WEBULL SDK adapter initialization started injected_client=%s",
                    sdk_client is not None)
        _suppress_official_sdk_logging()
        self.sdk_client = sdk_client or create_official_client(app_key, app_secret)
        self._snapshot_response_captured = False
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

    def stock_snapshot(self, symbols: Iterable[str], *, extended_hours: bool = False):
        """Return US-equity snapshots without requesting optional sessions by default."""
        symbols = list(symbols)
        if len(symbols) > MAX_SNAPSHOT_SYMBOLS:
            raise ValueError("Webull snapshot requests are limited to 100 symbols")
        method = self._operation(("get_snapshot", "get_stock_snapshot"))
        arguments = dict(symbols=",".join(symbols), category="US_STOCK")
        if extended_hours:
            arguments.update(extend_hour_required=True, overnight_required=True)
        try:
            response = method(**arguments)
        except TypeError:
            if not extended_hours:
                raise
            arguments.pop("overnight_required")
            arguments["include_overnight"] = True
            response = method(**arguments)
        self._capture_first_snapshot_response(response)
        return _plain(response)

    def _capture_first_snapshot_response(self, response) -> None:
        """Log the first successful snapshot result before Walter parses it."""
        if self._snapshot_response_captured:
            return
        self._snapshot_response_captured = True

        response_type = f"{type(response).__module__}.{type(response).__qualname__}"
        status = getattr(
            response, "status_code", getattr(response, "status", "<unavailable>")
        )
        headers = _safe_headers(getattr(response, "headers", {}))
        text = getattr(response, "text", "<unavailable>")
        if callable(text):
            text = text()
        text_preview = _body_text(text)[:500]

        decoded_json = "<unavailable>"
        json_method = getattr(response, "json", None)
        if callable(json_method):
            try:
                decoded_json = json_method()
            except Exception:
                decoded_json = "<JSON decoding failed>"

        LOGGER.info(
            "WEBULL first successful snapshot raw response type=%s status=%s "
            "headers=%s text_first_500=%s json=%s",
            response_type,
            status,
            headers,
            text_preview,
            _body_text(decoded_json),
        )

    @staticmethod
    def _history_arguments(arguments):
        """Translate Walter history arguments to the official SDK v2 signature."""
        normalized = dict(arguments)

        interval = normalized.pop("interval", normalized.pop("timeframe", None))
        if interval is not None and "timespan" not in normalized:
            interval_key = str(interval).strip().lower()
            timespans = {
                "m1": "M1", "1min": "M1", "1m": "M1",
                "m5": "M5", "5min": "M5", "5m": "M5",
                "m15": "M15", "15min": "M15", "15m": "M15",
                "m30": "M30", "30min": "M30", "30m": "M30",
                "m60": "M60", "60min": "M60", "1h": "M60",
                "d": "D", "1d": "D",
            }
            if interval_key in {"s30", "30sec", "30s"}:
                raise ValueError("Webull OpenAPI historical bars do not support 30-second timespan")
            normalized["timespan"] = timespans.get(interval_key, str(interval).upper())

        for key in ("start_time", "end_time"):
            value = normalized.get(key)
            if isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if key == "start_time" and not normalized.get("end_time"):
                        parsed = _clamp_future_session_start(parsed)
                    normalized[key] = int(parsed.timestamp() * 1000)
                except ValueError:
                    pass

        normalized["count"] = str(min(int(normalized.get("count", 200)), 1200))
        normalized.pop("extend_hour_required", None)
        include_overnight = normalized.pop("include_overnight", None)
        if include_overnight and not normalized.get("trading_sessions"):
            normalized["trading_sessions"] = "PRE,RTH,ATH"
        normalized.setdefault("real_time_required", True)
        return normalized

    def batch_bars(self, **arguments):
        """Call the SDK's official batch history operation without per-symbol delay."""
        method = self._operation(("get_batch_history_bar",))
        normalized = self._history_arguments(arguments)
        normalized["symbols"] = list(normalized.get("symbols", ()))
        return _plain(method(**normalized))

    def bars(self, **arguments):
        """Translate Walter bar arguments and isolate invalid history symbols."""
        method = self._operation(("get_history_bar",))
        normalized = self._history_arguments(arguments)

        _wait_for_history_bar_slot()
        try:
            response = _plain(method(**normalized))
        except Exception as exc:
            if _invalid_history_symbol(exc):
                LOGGER.warning(
                    "WEBULL history bars skipped invalid symbol symbol=%s error=%s",
                    normalized.get("symbol"), exc,
                )
                return {"data": []}
            raise
        if isinstance(response, dict) and isinstance(response.get("result"), list):
            response = {**response, "data": response["result"]}
        return response

    def stream(self, callback):
        factory = getattr(self.sdk_client, "_walter_streaming_client_factory", None)
        if factory is None:
            raise RuntimeError("Webull OpenAPI SDK lacks DataStreamingClient")
        client = factory()
        client.callback = callback
        return client
