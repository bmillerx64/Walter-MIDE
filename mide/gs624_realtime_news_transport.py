"""GS624: process-owned real-time Alpaca/Benzinga news WebSocket transport.

The socket is an independent push transport for news only. It never owns Streamlit
session state, AutoScan cadence, candidate/ranking/readiness authority, execution,
or orders. Received articles are normalized and deposited into GS620's completed
rolling cache; scans only read already-completed cache state.

Alpaca documents the endpoint as:
    wss://stream.data.alpaca.markets/v1beta1/news
with API-key/secret header authentication and marketwide news:["*"] subscription.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import json
import threading
import time
from typing import Any

from .news_provider import NewsArticle


UTC = timezone.utc
AUTHORITY = "NEWS_TRANSPORT_ONLY_REALTIME_PUSH"
DIAGNOSTIC_KEY = "gs624_realtime_news_transport"
STREAM_URL = "wss://stream.data.alpaca.markets/v1beta1/news"
_BUILD_OWNER = "_walter_gs624_realtime_news_transport_owner"
_RUNTIME_KEY = "_walter_gs624_realtime_news_runtime"
_RUNTIME_SCHEMA = 1
_MAX_BACKOFF_SECONDS = 60.0


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _new_runtime() -> dict[str, Any]:
    return {
        "schema": _RUNTIME_SCHEMA,
        "lock": threading.RLock(),
        "stop": threading.Event(),
        "thread": None,
        "status": "cold",
        "auth_status": "unknown",
        "subscription_status": "unknown",
        "last_connected_at": None,
        "last_disconnected_at": None,
        "last_message_at": None,
        "newest_article_at": None,
        "newest_article_age_at_receipt_seconds": None,
        "messages_received": 0,
        "articles_ingested": 0,
        "reconnect_count": 0,
        "last_error_type": None,
        "last_error_category": None,
        "last_error_code": None,
        "credential_source": None,
    }


def _runtime() -> dict[str, Any]:
    runtime = builtins.__dict__.get(_RUNTIME_KEY)
    if isinstance(runtime, dict) and runtime.get("schema") == _RUNTIME_SCHEMA:
        return runtime
    runtime = _new_runtime()
    builtins.__dict__[_RUNTIME_KEY] = runtime
    return runtime


def snapshot() -> dict:
    runtime = _runtime()
    with runtime["lock"]:
        thread = runtime.get("thread")
        return {
            "authority": AUTHORITY,
            "endpoint": STREAM_URL,
            "marketwide": True,
            "status": runtime.get("status"),
            "auth_status": runtime.get("auth_status"),
            "subscription_status": runtime.get("subscription_status"),
            "last_connected_at": runtime.get("last_connected_at"),
            "last_disconnected_at": runtime.get("last_disconnected_at"),
            "last_message_at": runtime.get("last_message_at"),
            "newest_article_at": runtime.get("newest_article_at"),
            "newest_article_age_at_receipt_seconds": runtime.get(
                "newest_article_age_at_receipt_seconds"
            ),
            "messages_received": int(runtime.get("messages_received") or 0),
            "articles_ingested": int(runtime.get("articles_ingested") or 0),
            "reconnect_count": int(runtime.get("reconnect_count") or 0),
            "last_error_type": runtime.get("last_error_type"),
            "last_error_category": runtime.get("last_error_category"),
            "last_error_code": runtime.get("last_error_code"),
            "credential_source": runtime.get("credential_source"),
            "thread_alive": bool(thread is not None and thread.is_alive()),
            "scan_blocked": False,
            "trading_authority_changed": False,
        }


def _classify_error(value: Any, *, code: Any = None) -> str:
    text = str(value or "").casefold()
    code_text = str(code or "").casefold()
    if "connection limit" in text or code_text == "406" or " 406 " in f" {text} ":
        return "connection_limit"
    if (
        "subscription" in text
        or "entitlement" in text
        or "not permitted" in text
        or "not authorized for" in text
    ):
        return "subscription_or_entitlement"
    if (
        "auth" in text
        or "unauthorized" in text
        or code_text in {"401", "402", "403"}
    ):
        return "authentication_or_entitlement"
    return "transport_error"


def _record_error(value: Any, *, code: Any = None) -> None:
    runtime = _runtime()
    with runtime["lock"]:
        runtime["last_error_type"] = type(value).__name__ if not isinstance(value, str) else "remote_error"
        runtime["last_error_category"] = _classify_error(value, code=code)
        runtime["last_error_code"] = str(code) if code is not None else None
        if runtime["status"] not in {"stopped", "unavailable"}:
            runtime["status"] = "degraded"


def _credentials_from_client(client: Any) -> tuple[str, str] | None:
    universe = getattr(client, "_universe_client", None)
    alpaca = getattr(universe, "client", universe)
    headers = getattr(alpaca, "headers", None)
    if not isinstance(headers, dict):
        return None
    key = str(headers.get("APCA-API-KEY-ID") or "").strip()
    secret = str(headers.get("APCA-API-SECRET-KEY") or "").strip()
    if not key or not secret:
        return None
    return key, secret


def _normalize_news(payload: dict) -> NewsArticle | None:
    if not isinstance(payload, dict):
        return None
    created = _utc(payload.get("created_at") or payload.get("updated_at"))
    headline = str(payload.get("headline") or "").strip()
    symbols = sorted({
        str(symbol).strip().upper()
        for symbol in payload.get("symbols", []) or []
        if str(symbol or "").strip()
    })
    if created is None or not headline or not symbols:
        return None
    return NewsArticle(
        id=str(payload.get("id") or f"stream:{created.isoformat()}:{headline}"),
        headline=headline,
        created_at=created,
        updated_at=_utc(payload.get("updated_at")),
        symbols=symbols,
        source=str(payload.get("source") or payload.get("author") or "Benzinga").strip(),
        url=str(payload.get("url") or "").strip() or None,
        provider="Alpaca realtime news",
    )


def _handle_message(ws: Any, raw: Any, *, received_at=None) -> None:
    runtime = _runtime()
    current = _utc(received_at) or datetime.now(UTC)
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        _record_error("invalid websocket JSON")
        return

    messages = payload if isinstance(payload, list) else [payload]
    for message in messages:
        if not isinstance(message, dict):
            continue
        kind = str(message.get("T") or "")
        if kind == "success":
            state = str(message.get("msg") or "").casefold()
            if state == "connected":
                with runtime["lock"]:
                    runtime["status"] = "connected"
                    runtime["last_connected_at"] = current.isoformat()
                    runtime["last_error_type"] = None
                    runtime["last_error_category"] = None
                    runtime["last_error_code"] = None
            elif state == "authenticated":
                with runtime["lock"]:
                    runtime["auth_status"] = "authenticated"
                    runtime["status"] = "authenticated"
                ws.send(json.dumps({"action": "subscribe", "news": ["*"]}))
            continue

        if kind == "subscription":
            news = message.get("news") or []
            subscribed = "*" in news
            with runtime["lock"]:
                runtime["subscription_status"] = (
                    "marketwide_subscribed" if subscribed else "unexpected_subscription"
                )
                runtime["status"] = "streaming" if subscribed else "degraded"
            continue

        if kind == "error":
            code = message.get("code")
            _record_error(message.get("msg") or "remote websocket error", code=code)
            with runtime["lock"]:
                if runtime.get("auth_status") != "authenticated":
                    runtime["auth_status"] = "rejected"
                elif runtime.get("subscription_status") != "marketwide_subscribed":
                    runtime["subscription_status"] = "rejected"
            continue

        if kind != "n":
            continue

        article = _normalize_news(message)
        with runtime["lock"]:
            runtime["messages_received"] = int(runtime.get("messages_received") or 0) + 1
            runtime["last_message_at"] = current.isoformat()
        if article is None:
            continue

        from . import gs620_live_news_stream as gs620

        trace = gs620.ingest_realtime_articles([article], received_at=current)
        age = max(0.0, (current - article.created_at).total_seconds())
        with runtime["lock"]:
            runtime["articles_ingested"] = int(runtime.get("articles_ingested") or 0) + 1
            previous = _utc(runtime.get("newest_article_at"))
            if previous is None or article.created_at >= previous:
                runtime["newest_article_at"] = article.created_at.isoformat()
                runtime["newest_article_age_at_receipt_seconds"] = round(age, 3)
            runtime["status"] = "streaming"
            runtime["last_error_type"] = None
            runtime["last_error_category"] = None
            runtime["last_error_code"] = None


def _on_open(_ws: Any) -> None:
    runtime = _runtime()
    now = datetime.now(UTC).isoformat()
    with runtime["lock"]:
        runtime["status"] = "connected"
        runtime["last_connected_at"] = now


def _on_error(_ws: Any, error: Any) -> None:
    _record_error(error)


def _on_close(_ws: Any, status_code: Any, _message: Any) -> None:
    runtime = _runtime()
    with runtime["lock"]:
        runtime["last_disconnected_at"] = datetime.now(UTC).isoformat()
        if runtime["status"] != "stopped":
            runtime["status"] = "disconnected"
    if status_code not in (None, 1000):
        _record_error(f"websocket close {status_code}", code=status_code)


def _connection_loop(api_key: str, secret: str) -> None:
    runtime = _runtime()
    backoff = 1.0
    while not runtime["stop"].is_set():
        try:
            import websocket

            ws = websocket.WebSocketApp(
                STREAM_URL,
                header=[
                    f"APCA-API-KEY-ID: {api_key}",
                    f"APCA-API-SECRET-KEY: {secret}",
                ],
                on_open=_on_open,
                on_message=lambda sock, message: _handle_message(sock, message),
                on_error=_on_error,
                on_close=_on_close,
            )
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as exc:
            _record_error(exc)

        if runtime["stop"].is_set():
            break
        with runtime["lock"]:
            runtime["reconnect_count"] = int(runtime.get("reconnect_count") or 0) + 1
            runtime["status"] = "reconnecting"
        runtime["stop"].wait(backoff)
        backoff = min(_MAX_BACKOFF_SECONDS, max(1.0, backoff * 2.0))


def ensure_realtime_news_stream(client: Any) -> dict:
    """Start exactly one process-owned news stream when credentials are available."""
    runtime = _runtime()
    credentials = _credentials_from_client(client)
    if credentials is None:
        with runtime["lock"]:
            runtime["status"] = "unavailable"
            runtime["auth_status"] = "credentials_missing"
            runtime["credential_source"] = "retained Alpaca client unavailable"
            runtime["last_error_category"] = "credentials_missing"
        return snapshot()

    with runtime["lock"]:
        thread = runtime.get("thread")
        if thread is not None and thread.is_alive():
            return snapshot()
        runtime["stop"].clear()
        runtime["status"] = "starting"
        runtime["auth_status"] = "pending"
        runtime["subscription_status"] = "pending"
        runtime["credential_source"] = "retained Alpaca client headers"
        runtime["last_error_type"] = None
        runtime["last_error_category"] = None
        runtime["last_error_code"] = None
        thread = threading.Thread(
            target=_connection_loop,
            args=credentials,
            name="walter-gs624-realtime-news",
            daemon=True,
        )
        runtime["thread"] = thread
        thread.start()
    return snapshot()


def install() -> None:
    """Start/observe GS624 from discovery without adding scan-path network waits."""
    from . import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _BUILD_OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(
        client,
        settings,
        news_items,
        *,
        universe_verification=None,
    ):
        provider = str(getattr(client, "provider_name", "") or "").upper()
        is_webull = (
            "WEBULL" in provider
            or "WEBULL" in client.__class__.__name__.upper()
        )
        if is_webull:
            trace = ensure_realtime_news_stream(client)
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics[DIAGNOSTIC_KEY] = deepcopy(trace)

        if universe_verification is None:
            return current(client, settings, news_items)
        return current(
            client,
            settings,
            news_items,
            universe_verification=universe_verification,
        )

    setattr(build_seed_symbols, _BUILD_OWNER, True)
    build_seed_symbols._gs624_original = current
    discovery.build_seed_symbols = build_seed_symbols


def _reset_for_tests() -> None:
    runtime = _runtime()
    with runtime["lock"]:
        runtime["stop"].set()
        thread = runtime.get("thread")
        fresh = _new_runtime()
        # Keep the same lock/stop objects only long enough to release a test thread.
        builtins.__dict__[_RUNTIME_KEY] = fresh
    if isinstance(thread, threading.Thread) and thread.is_alive():
        thread.join(timeout=0.2)


__all__ = [
    "AUTHORITY",
    "DIAGNOSTIC_KEY",
    "STREAM_URL",
    "snapshot",
    "ensure_realtime_news_stream",
    "install",
]
