"""GS540: warm-deploy-safe Discovery + News facade for shadow RVOL corroboration.

Phase 21 moved the implementation into Walter Next's authoritative Discovery + News
component. This historical module remains at its established startup/import point and
now resolves that authority lazily so a retained Streamlit generation cannot fail
because newer Discovery + News exports are absent.

The preserved authority contract is
DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL: this lane may add symbol
identity only when already-sampled GS523 page-2 RVOL evidence is corroborated by an
existing material-positive news catalyst. A stale generation admits no new symbol and
preserves incoming seeds/reasons. Participation, expansion, Mission Ranking, readiness,
alerts, execution, and orders remain unchanged.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


UTC = timezone.utc
AUTHORITY = "DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL"
SHADOW_LIMIT = 20
MIN_SHADOW_RVOL = 2.0
NEWS_LOOKBACK = timedelta(hours=6)
_OWNER = "_walter_gs540_news_corroborated_shadow_rvol_owner"

_EXPORTS = {
    "_number": "_shadow_rvol_number",
    "_now_utc": "shadow_rvol_now_utc",
    "shadow_rvol_rows": "shadow_rvol_rows",
    "eligible_shadow_rows": "eligible_shadow_rvol_rows",
    "_fetch_targeted_articles": "fetch_shadow_rvol_targeted_articles",
    "merge_news_corroborated_shadow_rvol": "merge_news_corroborated_shadow_rvol",
}


def _news():
    from mide.authorities import discovery_news

    return discovery_news


def _fallback_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fallback_now_utc(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fallback_rows(_client) -> list[dict]:
    return []


def _fallback_eligible(_rows) -> list[dict]:
    return []


def _fallback_fetch(_symbols, *, now) -> list:
    return []


def _fallback_merge(
    _client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
    fetcher=None,
):
    output = list(seeds or [])
    updated_reasons = {
        str(symbol): list(values)
        for symbol, values in (reasons or {}).items()
    }
    return output, updated_reasons, {
        "authority": AUTHORITY,
        "shadow_rows_seen": 0,
        "eligible_shadow_symbols": [],
        "request_made": False,
        "articles_received": 0,
        "material_corroborations": [],
        "symbols_added": [],
        "reason": "Discovery + News unavailable in retained runtime",
        "trading_authority_changed": False,
    }


_FALLBACKS = {
    "_number": _fallback_number,
    "_now_utc": _fallback_now_utc,
    "shadow_rvol_rows": _fallback_rows,
    "eligible_shadow_rows": _fallback_eligible,
    "_fetch_targeted_articles": _fallback_fetch,
    "merge_news_corroborated_shadow_rvol": _fallback_merge,
}


def install() -> None:
    """Install GS540 when the warm Discovery + News generation supports it."""
    current = getattr(
        _news(),
        "install_news_corroborated_shadow_rvol",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is not None:
        value = getattr(_news(), target, None)
        if callable(value):
            return value
        return _FALLBACKS[name]
    try:
        return getattr(_news(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "SHADOW_LIMIT",
    "MIN_SHADOW_RVOL",
    "NEWS_LOOKBACK",
    "shadow_rvol_rows",
    "eligible_shadow_rows",
    "merge_news_corroborated_shadow_rvol",
    "install",
]
