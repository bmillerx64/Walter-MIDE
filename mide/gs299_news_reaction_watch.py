"""GS299: keep fresh news-seeded symbols under observation through reaction window.

GS298 lets fresh material FMP Stock News add ticker identities to Webull discovery.
That market-wide feed is intentionally bounded to the newest 100 articles, so a
still-valid catalyst can disappear from page 0 before Walter's six-hour catalyst
window expires.  GS299 preserves only the news-watch identity/provenance until
that original six-hour window expires.

No stale price, volume, score, qualification, rank, readiness, trigger, or
execution state is carried.  Retained symbols must receive fresh Webull evidence
and pass the complete normal pipeline on every scan.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping

from .gs298_news_seeded_discovery import (
    NEWS_SEED_FRESHNESS,
    NEWS_SEED_LIMIT,
    NEWS_SEED_REASON,
    _is_webull_client,
)

UTC = timezone.utc
REACTION_WATCH_REASON = "GS299 active news reaction watch"
REACTION_WATCH_STATE_KEY = "walter_news_reaction_watch"


def _utc(value) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _now_utc(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def update_reaction_watch(
    existing: Mapping[str, Mapping[str, object]] | None,
    current_evidence: Iterable[Mapping[str, object]],
    *,
    now=None,
) -> dict[str, dict]:
    """Expire old watches and refresh current GS298 material-news identities."""
    current = _now_utc(now)
    output: dict[str, dict] = {}

    for raw_symbol, raw in (existing or {}).items():
        symbol = str(raw_symbol or "").strip().upper()
        expires_at = _utc((raw or {}).get("expires_at"))
        if symbol and expires_at is not None and expires_at > current:
            output[symbol] = dict(raw)

    for raw in current_evidence or []:
        symbol = str(raw.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        try:
            age_minutes = max(0.0, float(raw.get("age_minutes") or 0.0))
        except (TypeError, ValueError):
            continue
        published_at = current - timedelta(minutes=age_minutes)
        expires_at = published_at + NEWS_SEED_FRESHNESS
        if expires_at <= current:
            continue
        output[symbol] = {
            "symbol": symbol,
            "source": str(raw.get("source") or "FMP"),
            "headline": str(raw.get("headline") or ""),
            "catalyst_score": raw.get("catalyst_score"),
            "catalyst_flags": list(raw.get("catalyst_flags") or []),
            "trusted_source": bool(raw.get("trusted_source")),
            "published_at": published_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    return output


def merge_reaction_watch(
    seeds: list[str],
    reasons: dict[str, list[str]],
    watch: Mapping[str, Mapping[str, object]],
    *,
    limit: int = NEWS_SEED_LIMIT,
) -> tuple[list[str], dict[str, list[str]], list[dict]]:
    """Merge watched ticker identities only, newest catalyst first and bounded."""
    output = list(seeds)
    existing = {str(symbol or "").strip().upper() for symbol in output}
    candidates = []
    for symbol, raw in (watch or {}).items():
        published = _utc((raw or {}).get("published_at")) or datetime.min.replace(tzinfo=UTC)
        candidates.append((published, str(symbol).upper(), dict(raw)))
    candidates.sort(reverse=True)

    added: list[dict] = []
    for _published, symbol, raw in candidates:
        if len(added) >= max(0, int(limit)):
            break
        if not symbol or symbol in existing:
            continue
        source = str(raw.get("source") or "FMP").strip()
        output.append(symbol)
        existing.add(symbol)
        reasons.setdefault(symbol, []).append(f"{REACTION_WATCH_REASON}: {source}")
        added.append(raw)
    return output, reasons, added


def install() -> None:
    """Wrap discovery after GS298 and preserve only still-fresh news watch IDs."""
    from . import discovery

    original = discovery.build_seed_symbols
    if getattr(original, "_gs299_installed", False):
        return

    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = original(client, settings, news_items)
        else:
            seeds, reasons = original(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        if not _is_webull_client(client):
            return seeds, reasons

        diagnostics = getattr(client, "diagnostics", None)
        try:
            import streamlit as st

            current_news = (
                (diagnostics or {}).get("news_seeded_discovery", {}).get("evidence", [])
                if isinstance(diagnostics, dict)
                else []
            )
            prior = st.session_state.get(REACTION_WATCH_STATE_KEY, {})
            watch = update_reaction_watch(prior, current_news)
            st.session_state[REACTION_WATCH_STATE_KEY] = watch
            seeds, reasons, retained = merge_reaction_watch(seeds, reasons, watch)

            if isinstance(diagnostics, dict):
                diagnostics["news_reaction_watch"] = {
                    "active": bool(watch),
                    "freshness_hours": int(NEWS_SEED_FRESHNESS.total_seconds() // 3600),
                    "watch_symbols": sorted(watch),
                    "watch_count": len(watch),
                    "retained_symbols_added": [item.get("symbol") for item in retained],
                    "retained_count": len(retained),
                    "safety": "ticker/news provenance only; fresh Webull evidence required every scan",
                }
                diagnostics["final_seed_count"] = len(seeds)
        except Exception as exc:
            # This is resilience only. Never let watch-state mechanics interfere
            # with GS298/native discovery, and avoid persisting exception text.
            if isinstance(diagnostics, dict):
                diagnostics["news_reaction_watch"] = {
                    "active": False,
                    "error_type": type(exc).__name__,
                    "retained_count": 0,
                    "fallback": "GS298/native Webull discovery unchanged",
                }
        return seeds, reasons

    build_seed_symbols._gs299_installed = True
    build_seed_symbols._gs299_original = original
    discovery.build_seed_symbols = build_seed_symbols
