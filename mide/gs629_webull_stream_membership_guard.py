"""GS629: keep Webull TICK membership inside the provider's supported boundary.

Friday 2026-10-02 live evidence showed the optional Webull TICK lane repeatedly
failing while the canonical REST scanner remained healthy. The retained universe
was 105-114 symbols, Webull rejected stream subscriptions above 100 symbols, and
several symbols were explicitly rejected as INVALID_SYMBOL. Because the failed
subscription produced zero ticks, GS627 had no genuine live 30-second evidence.

GS629 changes only the symbol list handed to the already-established TICK stream:
- preserve caller order and deduplicate symbols;
- remove symbols already proven unsupported by Webull snapshot/stream diagnostics;
- cap the requested stream membership at 100 total symbols;
- if Webull explicitly identifies additional INVALID_SYMBOL names, remember them
  and make one bounded retry with those names removed;
- when an INVALID_SYMBOL add poisons an existing transport, retire only that failed
  subscription before the bounded retry.

REST snapshots/history, discovery membership, candidate ranking, scanner state,
Entry/audio authority, execution and orders remain unchanged.
"""
from __future__ import annotations

from functools import wraps
import re
from typing import Callable, Iterable


AUTHORITY = "WEBULL_TICK_STREAM_MEMBERSHIP_GUARD"
MAX_STREAM_SYMBOLS = 100
MAX_INVALID_RETRIES = 1
_OWNER = "_walter_gs629_stream_membership_guard"
REVISION = 1

_INVALID_STREAM_SYMBOLS = re.compile(
    r"symbols?\s+does\s+not\s+exist\s+in\s+the\s+category\s*\.\s*\[([^\[\]]+)\]",
    re.IGNORECASE,
)


def _symbols(values: Iterable[str]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value or "").strip().upper()
            for value in values or []
            if str(value or "").strip()
        )
    )


def _stream(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        try:
            provider.diagnostics = diagnostics
        except Exception:
            return {}
    stream = diagnostics.get("webull_stream")
    if not isinstance(stream, dict):
        stream = {}
        diagnostics["webull_stream"] = stream
    return stream


def _explicit_invalid_symbols(value) -> tuple[str, ...]:
    text = str(value or "")
    if "INVALID_SYMBOL" not in text.upper():
        return ()
    match = _INVALID_STREAM_SYMBOLS.search(text)
    if not match:
        return ()
    values = [
        part.strip().upper()
        for part in match.group(1).split(",")
        if part.strip()
    ]
    if not values or any(
        not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", symbol)
        for symbol in values
    ):
        return ()
    return tuple(dict.fromkeys(values))


def _known_invalid(provider, trace: dict) -> set[str]:
    stream = _stream(provider)
    values = set(_symbols(stream.get("snapshot_unsupported_symbols") or []))
    values.update(_symbols(trace.get("invalid_symbols") or []))
    return values


def _retire_failed_subscription(provider, trace: dict) -> None:
    subscription = getattr(provider, "_subscription", None)
    if subscription is None:
        return
    try:
        subscription.close()
    except Exception as exc:
        trace["failed_subscription_cleanup_error_type"] = type(exc).__name__
    finally:
        try:
            provider._subscription = None
        except Exception:
            pass
        subscribed = getattr(provider, "_subscribed", None)
        if hasattr(subscribed, "clear"):
            subscribed.clear()
        trace["failed_subscription_retired"] = True


def ensure_stream_with_membership_guard(
    original: Callable,
    provider,
    symbols: Iterable[str],
):
    requested = _symbols(symbols)
    stream = _stream(provider)
    trace = stream.get("gs629_stream_membership")
    if not isinstance(trace, dict):
        trace = {
            "authority": AUTHORITY,
            "invalid_symbols": [],
            "invalid_retry_total": 0,
            "failed_subscription_retirements": 0,
            "rest_snapshot_history_unchanged": True,
            "discovery_membership_changed": False,
            "trading_authority_changed": False,
            "audio_authority_changed": False,
            "execution_authority_changed": False,
        }
        stream["gs629_stream_membership"] = trace

    invalid = _known_invalid(provider, trace)
    retries = 0

    while True:
        eligible = [symbol for symbol in requested if symbol not in invalid]
        selected = eligible[:MAX_STREAM_SYMBOLS]
        omitted_cap = eligible[MAX_STREAM_SYMBOLS:]
        omitted_invalid = [symbol for symbol in requested if symbol in invalid]

        trace.update(
            requested_symbol_count=len(requested),
            requested_symbols=list(requested),
            selected_symbol_count=len(selected),
            selected_symbols=list(selected),
            omitted_due_cap_count=len(omitted_cap),
            omitted_due_cap_symbols=list(omitted_cap),
            omitted_invalid_count=len(omitted_invalid),
            omitted_invalid_symbols=list(omitted_invalid),
            invalid_symbols=sorted(invalid),
            max_stream_symbols=MAX_STREAM_SYMBOLS,
            invalid_retries_last_call=retries,
        )

        if not selected:
            trace["last_result"] = False
            trace["last_failure_reason"] = "no_supported_stream_symbols"
            return False

        failures_before = list(stream.get("subscription_failures") or [])
        result = original(selected)
        failures_after = list(stream.get("subscription_failures") or [])

        trace["last_result"] = bool(result)
        trace["subscribed_symbol_count_after"] = len(
            getattr(provider, "_subscribed", set()) or set()
        )
        trace["subscribed_symbols_after"] = sorted(
            getattr(provider, "_subscribed", set()) or set()
        )

        if result:
            trace["last_failure_reason"] = None
            return result

        newest = (
            failures_after[-1]
            if len(failures_after) > len(failures_before)
            else None
        )
        newly_invalid = [
            symbol
            for symbol in _explicit_invalid_symbols(newest)
            if symbol not in invalid
        ]
        if not newly_invalid or retries >= MAX_INVALID_RETRIES:
            trace["last_failure_reason"] = (
                "invalid_symbol_retry_exhausted"
                if newly_invalid
                else "delegate_stream_failure"
            )
            return result

        invalid.update(newly_invalid)
        trace["invalid_symbols"] = sorted(invalid)
        retries += 1
        trace["invalid_retries_last_call"] = retries
        trace["invalid_retry_total"] = int(trace.get("invalid_retry_total") or 0) + 1

        if getattr(provider, "_subscription", None) is not None:
            _retire_failed_subscription(provider, trace)
            trace["failed_subscription_retirements"] = int(
                trace.get("failed_subscription_retirements") or 0
            ) + 1


def install_for_provider(provider) -> bool:
    if provider is None:
        return False
    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)
    if (
        getattr(function, _OWNER, None) == REVISION
        or getattr(current, _OWNER, None) == REVISION
    ):
        return False

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_membership_guard(
            current,
            provider,
            symbols,
        )

    setattr(guarded, _OWNER, REVISION)
    guarded._gs629_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    return True


__all__ = [
    "AUTHORITY",
    "MAX_STREAM_SYMBOLS",
    "REVISION",
    "ensure_stream_with_membership_guard",
    "install_for_provider",
]
