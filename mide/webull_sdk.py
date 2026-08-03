"""Thin, mockable boundary around the official Webull OpenAPI Python SDK."""

from __future__ import annotations

from importlib import import_module
from typing import Iterable


HTTP_HOST = "https://api.webull.com"
STREAM_HOST = "data-api.webull.com"
SNAPSHOT_OPERATION = "GET /openapi/market-data/stock/snapshot"
MAX_SNAPSHOT_SYMBOLS = 100


def create_official_client(app_key: str, app_secret: str):
    """Construct the SDK client without implementing authentication locally.

    Releases of the official distribution have exposed both a convenience
    client and an OpenAPI-generated client.  Supporting those public layouts
    here also keeps the rest of Walter independent of SDK packaging details.
    """
    errors = []
    for module_name, class_name in (
        ("webull", "WebullClient"),
        ("webull.openapi", "ApiClient"),
        ("webull.openapi.api_client", "ApiClient"),
        ("webull_openapi", "ApiClient"),
    ):
        try:
            cls = getattr(import_module(module_name), class_name)
            try:
                return cls(app_key=app_key, app_secret=app_secret, base_url=HTTP_HOST)
            except TypeError:
                return cls(app_key, app_secret)
        except (ImportError, AttributeError, TypeError) as exc:
            errors.append(f"{module_name}.{class_name}: {exc}")
    raise RuntimeError(
        "Official webull-openapi-python-sdk client could not be initialized: "
        + " | ".join(errors)
    )


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
        self.sdk_client = sdk_client or create_official_client(app_key, app_secret)

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
        method = self._operation(("get_stock_snapshot", "stock_snapshot", "get_stock_snapshots"))
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
        method = self._operation(("get_bars", "get_stock_bars", "stock_bars"))
        return _plain(method(**arguments))

    def stream(self, callback):
        method = self._operation(("market_data_stream", "create_market_data_stream", "stream"))
        return method(callback=callback, host=STREAM_HOST)
