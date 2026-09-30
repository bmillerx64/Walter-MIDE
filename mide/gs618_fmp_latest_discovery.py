"""GS618: warm-deploy-safe facade for continuous FMP latest-news discovery.

Discovery + News owns the implementation. GS618 promotes FMP's documented
marketwide ``news/stock-latest`` feed into Walter's existing GS298 identity-only
news seed seam. It never grants catalyst score, readiness, execution, or order
authority by itself.
"""
from __future__ import annotations

from mide.authorities import discovery_news as _news


AUTHORITY = _news.AUTHORITY
ENDPOINT = _news.FMP_LATEST_DISCOVERY_ENDPOINT


def install() -> None:
    _news.install_fmp_latest_news_discovery()


def __getattr__(name: str):
    try:
        return getattr(_news, name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "ENDPOINT",
    "install",
]
