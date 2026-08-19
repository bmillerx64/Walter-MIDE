"""GS301: preserve fresh discovery-news evidence into Catalyst Assessment.

GS298/300 can discover a ticker from market-wide FMP Stock News and GS299 can
retain that ticker through the original six-hour reaction window.  Catalyst
Assessment subsequently performs an independent symbol-specific news request.
If that second request omits the original article, Walter can forget the very
catalyst that caused the ticker to enter surveillance.

This layer bridges only the already-observed article provenance.  It never
carries price, volume, technicals, score, qualification, rank, readiness,
trigger, order, or execution state.  The handoff article must still be inside
its original GS299 expiry and must still classify as a positive material
catalyst under Walter's current classifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Mapping

from .gs299_news_reaction_watch import REACTION_WATCH_STATE_KEY

UTC = timezone.utc


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


def catalyst_handoff_articles(
    watch: Mapping[str, Mapping[str, object]] | None,
    *,
    requested_symbols: Iterable[str],
    now=None,
) -> list[dict]:
    """Rehydrate still-fresh material article provenance for requested symbols."""
    from .news import MATERIAL_CATALYST_SCORE, classify_headline

    current = _now_utc(now)
    requested = {
        str(symbol or "").strip().upper()
        for symbol in requested_symbols or []
        if str(symbol or "").strip()
    }
    output: list[dict] = []

    for raw_symbol, raw in (watch or {}).items():
        symbol = str(raw_symbol or "").strip().upper()
        item = raw or {}
        if not symbol or symbol not in requested:
            continue
        published = _utc(item.get("published_at"))
        expires = _utc(item.get("expires_at"))
        if published is None or expires is None or expires <= current or published > current:
            continue

        headline = str(item.get("headline") or "").strip()
        source = str(item.get("source") or "").strip() or "FMP"
        score, flags = classify_headline(headline)
        # Defense in depth: session state is provenance, not authority.  Re-run
        # the current classifier so a stale/tampered neutral or negative record
        # can never be promoted merely because it exists in the watch cache.
        if float(score or 0) < MATERIAL_CATALYST_SCORE:
            continue

        output.append(
            {
                "id": f"gs301:{symbol}:{published.isoformat()}:{headline.casefold()}",
                "headline": headline,
                "created_at": published.isoformat(),
                "updated_at": None,
                "symbols": [symbol],
                "source": source,
                "url": None,
                "provider": "Financial Modeling Prep",
                "gs301_handoff": True,
                "gs301_catalyst_score": float(score),
                "gs301_catalyst_flags": list(flags),
            }
        )
    return sorted(output, key=lambda item: item["created_at"], reverse=True)


def merge_catalyst_handoff(
    fetched: Iterable[dict],
    handoff: Iterable[dict],
) -> tuple[list[dict], list[str]]:
    """Merge exact article provenance without duplicating provider-returned news."""
    output = [dict(item) for item in (fetched or [])]
    seen = {
        (
            str(item.get("source") or "").strip().casefold(),
            str(item.get("headline") or "").strip().casefold(),
            tuple(sorted(str(s).strip().upper() for s in (item.get("symbols") or []))),
        )
        for item in output
    }
    added_symbols: list[str] = []

    for raw in handoff or []:
        item = dict(raw)
        key = (
            str(item.get("source") or "").strip().casefold(),
            str(item.get("headline") or "").strip().casefold(),
            tuple(sorted(str(s).strip().upper() for s in (item.get("symbols") or []))),
        )
        if key in seen:
            continue
        output.append(item)
        seen.add(key)
        for symbol in item.get("symbols") or []:
            canonical = str(symbol or "").strip().upper()
            if canonical and canonical not in added_symbols:
                added_symbols.append(canonical)

    output.sort(
        key=lambda item: _utc(item.get("created_at") or item.get("updated_at"))
        or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    return output, added_symbols


def _session_watch() -> Mapping[str, Mapping[str, object]]:
    try:
        import streamlit as st

        value = st.session_state.get(REACTION_WATCH_STATE_KEY, {})
        return value if isinstance(value, Mapping) else {}
    except Exception:
        return {}


def install() -> None:
    """Augment symbol-specific NewsService results with fresh GS299 provenance."""
    from .news_provider import NewsService

    if getattr(NewsService, "_gs301_installed", False):
        return

    original_fetch = NewsService.fetch

    def fetch(self, *, symbols=(), initial_lookback=None, force_lookback=False):
        kwargs = {"symbols": symbols, "force_lookback": force_lookback}
        if initial_lookback is not None:
            kwargs["initial_lookback"] = initial_lookback
        fetched = original_fetch(self, **kwargs)

        requested = [
            str(symbol or "").strip().upper()
            for symbol in symbols or []
            if str(symbol or "").strip()
        ]
        handoff = catalyst_handoff_articles(
            _session_watch(), requested_symbols=requested
        )
        merged, added_symbols = merge_catalyst_handoff(fetched, handoff)
        self.metrics["catalyst_handoff"] = {
            "active": bool(added_symbols),
            "symbols": added_symbols,
            "count": len(added_symbols),
            "source": "GS298/GS299 FMP discovery provenance",
            "safety": "article provenance only; no market/trading state carried",
        }
        return merged

    NewsService.fetch = fetch
    NewsService._gs301_installed = True
