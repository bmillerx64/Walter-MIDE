"""GS469: restore genuine 30-second Webull stream continuity across warm deploys.

Fresh Flight Recorder evidence on 2026-09-16 exposed a hard break in Walter's
bottom-up attention model. Genuine ``observational_30s`` evidence was present on every
scan through build ``50d8eaa07e30`` and disappeared exactly when build
``01d6f8c7e81f`` went live. It remained absent through current build ``af3739978ef3``.
The downstream GS390 validation rows likewise carried no 30-second snapshot, so the
30s -> 1m -> 3m model was effectively beginning at 1m.

The stream architecture had two continuity assumptions that are unsafe under a warm
Streamlit deployment:

* GS379's authoritative provider is kept in a process/module-global weakref and was
  registered only when ``LiveWebullProvider`` was constructed. A retained provider
  can therefore outlive the module generation that owned that registry.
* ``ensure_stream`` historically treated a non-null subscription with no newly added
  symbols as healthy without checking whether Webull TICK messages were still
  arriving. A dead transport could therefore survive scan after scan.

GS469 repairs those two ownership/liveness seams at the existing stream boundary.
Every live scan reasserts its persistent provider as GS379's active 30s source. During
Webull's extended trading window, a subscribed transport with no TICK heartbeat or a
heartbeat older than three minutes is retired and resubscribed. Restarts are rate
limited to five minutes. If the last retained 30s bar belongs to a prior Eastern
trading day, that stale session buffer is cleared before reconnection so yesterday's
30s state cannot masquerade as current evidence.

Safety contract:
- the only 30s source remains genuine Webull OpenAPI TICK data;
- no synthetic 30s bars and no unsupported historical 30s REST fallback are added;
- snapshot/history market-data authority is unchanged if the stream is unavailable;
- no discovery, scoring, ranking, VWAP/ST formula, qualification, readiness, alert,
  execution, session-entry, or order threshold changes;
- outside 04:00-20:00 ET weekdays GS469 never forces a reconnect.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from functools import wraps
from typing import Any


AUTHORITY = "LIVE_30S_STREAM_CONTINUITY"
STALE_TICK_SECONDS = 180.0
RESTART_COOLDOWN_SECONDS = 300.0
STREAM_START_ET = time(4, 0)
STREAM_END_ET = time(20, 0)
_OWNER_ATTR = "_walter_gs469_30s_stream_continuity_owner"


def _utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now_ms(value: datetime | None = None) -> int:
    return int(_utc(value).timestamp() * 1000)


def _market_stream_expected(value: datetime | None = None) -> bool:
    """Return whether Walter should reasonably be receiving U.S. equity TICKs."""
    from .time_service import eastern_time

    current = eastern_time(_utc(value))
    clock = current.time().replace(tzinfo=None)
    return current.weekday() < 5 and STREAM_START_ET <= clock < STREAM_END_ET


def _stream_diagnostics(provider) -> dict:
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


def _last_tick_ms(provider) -> int | None:
    raw = _stream_diagnostics(provider).get("last_tick_timestamp_ms")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _tick_age_seconds(provider, value: datetime | None = None) -> float | None:
    last = _last_tick_ms(provider)
    if last is None:
        return None
    return max(0.0, (_now_ms(value) - last) / 1000.0)


def _active_registry_provider():
    from . import gs379_webull_stream_data_truth as gs379

    reference = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def reassert_active_provider(provider) -> bool:
    """Rebind a retained provider when a warm module generation lost GS379's weakref."""
    if provider is None or not getattr(provider, "_enable_streaming", False):
        return False
    if _active_registry_provider() is provider:
        return False

    from . import gs379_webull_stream_data_truth as gs379

    gs379._register_active_provider(provider)
    stream = _stream_diagnostics(provider)
    stream["gs469_active_provider_rebinds"] = int(
        stream.get("gs469_active_provider_rebinds", 0) or 0
    ) + 1
    return True


def _subscription_started_ms(provider) -> int | None:
    raw = getattr(provider, "_gs469_subscription_started_ms", None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _restart_cooldown_active(provider, value: datetime | None = None) -> bool:
    raw = getattr(provider, "_gs469_last_restart_attempt_ms", None)
    try:
        last = int(raw)
    except (TypeError, ValueError):
        return False
    return (_now_ms(value) - last) / 1000.0 < RESTART_COOLDOWN_SECONDS


def _restart_reason(provider, value: datetime | None = None) -> str | None:
    """Return a bounded liveness failure reason for an already-open subscription."""
    if not getattr(provider, "_enable_streaming", False):
        return None
    if not _market_stream_expected(value):
        return None
    if getattr(provider, "_subscription", None) is None:
        return None
    if not set(getattr(provider, "_subscribed", set()) or set()):
        return None
    if _restart_cooldown_active(provider, value):
        return None

    age = _tick_age_seconds(provider, value)
    if age is not None:
        if age > STALE_TICK_SECONDS:
            return f"last Webull TICK heartbeat is {age:.1f}s old"
        return None

    # A subscription opened by this wrapper gets a full stale window before Walter
    # judges it. A subscription inherited from an earlier module generation has no
    # such marker; if it has never produced a TICK, repair it immediately.
    started = _subscription_started_ms(provider)
    if started is not None:
        elapsed = max(0.0, (_now_ms(value) - started) / 1000.0)
        if elapsed <= STALE_TICK_SECONDS:
            return None
    return "subscribed Webull transport has no observed TICK heartbeat"


def _latest_30s_bar_ms(provider) -> int | None:
    latest = None
    current = getattr(provider, "_gs379_30s_current", None)
    if isinstance(current, dict):
        for row in current.values():
            try:
                stamp = int((row or {}).get("t"))
            except (TypeError, ValueError):
                continue
            latest = stamp if latest is None else max(latest, stamp)
    closed = getattr(provider, "_gs379_30s_closed", None)
    if isinstance(closed, dict):
        for rows in closed.values():
            if not rows:
                continue
            try:
                stamp = int((rows[-1] or {}).get("t"))
            except (TypeError, ValueError, KeyError):
                continue
            latest = stamp if latest is None else max(latest, stamp)
    return latest


def _clear_prior_session_30s(provider, value: datetime | None = None) -> bool:
    """Clear only a prior-Eastern-day 30s cache before a forced reconnect."""
    latest = _latest_30s_bar_ms(provider)
    if latest is None:
        return False

    from .time_service import eastern_time

    latest_day = eastern_time(datetime.fromtimestamp(latest / 1000.0, tz=timezone.utc)).date()
    current_day = eastern_time(_utc(value)).date()
    if latest_day >= current_day:
        return False

    lock = getattr(provider, "_lock", None)
    if lock is None:
        return False
    with lock:
        current = getattr(provider, "_gs379_30s_current", None)
        closed = getattr(provider, "_gs379_30s_closed", None)
        if isinstance(current, dict):
            current.clear()
        if isinstance(closed, dict):
            closed.clear()
    return True


def ensure_stream_continuity(original, provider, symbols, *, now: datetime | None = None):
    """Reassert source ownership, repair stale TICK transport, then preserve base behavior."""
    if not getattr(provider, "_enable_streaming", False):
        return original(provider, symbols)

    now = _utc(now)
    now_ms = _now_ms(now)
    rebound = reassert_active_provider(provider)
    reason = _restart_reason(provider, now)
    restarted = False
    cleared_prior_session = False

    if reason:
        from . import gs379_webull_stream_data_truth as gs379

        provider._gs469_last_restart_attempt_ms = now_ms
        cleared_prior_session = _clear_prior_session_30s(provider, now)
        gs379._retire_provider_stream(provider)
        restarted = True

    result = original(provider, symbols)

    if getattr(provider, "_subscription", None) is not None:
        if restarted or _subscription_started_ms(provider) is None:
            provider._gs469_subscription_started_ms = now_ms

    stream = _stream_diagnostics(provider)
    if restarted:
        stream["gs469_stale_stream_restarts"] = int(
            stream.get("gs469_stale_stream_restarts", 0) or 0
        ) + 1
    stream["gs469_30s_stream_continuity"] = {
        "authority": AUTHORITY,
        "active_provider_reasserted": bool(rebound),
        "stream_expected_now": _market_stream_expected(now),
        "subscription_present": getattr(provider, "_subscription", None) is not None,
        "subscribed_symbols": len(set(getattr(provider, "_subscribed", set()) or set())),
        "last_tick_age_seconds": (
            round(_tick_age_seconds(provider, now), 1)
            if _tick_age_seconds(provider, now) is not None
            else None
        ),
        "restart_performed": bool(restarted),
        "restart_reason": reason,
        "prior_session_30s_cleared": bool(cleared_prior_session),
        "restart_cooldown_seconds": RESTART_COOLDOWN_SECONDS,
        "stale_tick_seconds": STALE_TICK_SECONDS,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    return result


def install() -> None:
    """Install outside GS379/GS389 so retained provider instances self-heal per scan."""
    from . import webull_live

    current = webull_live.LiveWebullProvider.ensure_stream
    if getattr(current, _OWNER_ATTR, False):
        return

    @wraps(current)
    def ensure_stream(self, symbols):
        return ensure_stream_continuity(current, self, symbols)

    ensure_stream._gs469_30s_stream_continuity = True
    ensure_stream._gs469_original = current
    setattr(ensure_stream, _OWNER_ATTR, True)
    webull_live.LiveWebullProvider.ensure_stream = ensure_stream
