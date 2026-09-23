"""GS540: historical compatibility facade for news-corroborated shadow RVOL.

Phase 21 moves the implementation into Walter Next's authoritative Discovery + News
component. GS540 remains at its historical startup/import point so its established
tests and monkeypatch surface remain valid.

The preserved authority contract is
DISCOVERY_IDENTITY_ONLY_NEWS_CORROBORATED_SHADOW_RVOL: this lane may add symbol
identity only when already-sampled GS523 page-2 RVOL evidence is corroborated by an
existing material-positive news catalyst. It does not change participation, expansion,
Mission Ranking, readiness, alerts, execution, or orders.
"""
from __future__ import annotations

from mide.authorities import discovery_news as _news


UTC = _news.UTC
AUTHORITY = _news.SHADOW_RVOL_AUTHORITY
SHADOW_LIMIT = _news.SHADOW_RVOL_LIMIT
MIN_SHADOW_RVOL = _news.SHADOW_RVOL_MIN
NEWS_LOOKBACK = _news.SHADOW_RVOL_NEWS_LOOKBACK
_OWNER = _news._SHADOW_RVOL_OWNER

_number = _news._shadow_rvol_number
_now_utc = _news.shadow_rvol_now_utc
shadow_rvol_rows = _news.shadow_rvol_rows
eligible_shadow_rows = _news.eligible_shadow_rvol_rows
_fetch_targeted_articles = _news.fetch_shadow_rvol_targeted_articles
merge_news_corroborated_shadow_rvol = _news.merge_news_corroborated_shadow_rvol


def install() -> None:
    """Install GS540 through authoritative Discovery + News ownership."""
    _news.install_news_corroborated_shadow_rvol()


def __getattr__(name: str):
    try:
        return getattr(_news, name)
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
