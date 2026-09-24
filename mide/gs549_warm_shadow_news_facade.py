"""GS549: warm-deploy-safe facade for Alpaca shadow-news observation.

GS544 intentionally reads Alpaca news only as bounded forensic shadow evidence. A
warm Streamlit runtime can retain a pre-GS544 LiveWebullProvider whose private
symbol-master facade predates AlpacaProvider.news(). Replacing that retained
universe client would change an active provider dependency, so GS549 instead wraps
only the observer call with a detached facade that shares diagnostics while pointing
at a current news-capable Alpaca client.

No discovery, catalyst, ranking, readiness, execution, or order authority changes.
"""
from __future__ import annotations

from typing import Any, Callable


AUTHORITY = "WARM_DEPLOY_SHADOW_NEWS_FACADE"
_CLIENT_ATTR = "_gs549_shadow_news_client"


class _ShadowObserverClient:
    """Minimal client view required by GS544's observation-only helper."""

    def __init__(self, source_client: Any, news_client: Any):
        self._universe_client = news_client
        diagnostics = getattr(source_client, "diagnostics", None)
        self.diagnostics = diagnostics if isinstance(diagnostics, dict) else {}


def observer_client(
    client: Any,
    news_client_factory: Callable[[], Any],
) -> tuple[Any, bool]:
    """Return a GS544-safe client view without mutating the active universe facade.

    Current providers already expose a news-capable private universe client and pass
    through unchanged. Warm-retained legacy providers receive one lazily cached,
    shadow-only Alpaca client behind a detached observer facade.
    """
    retained = getattr(client, "_universe_client", None)
    if callable(getattr(retained, "news", None)):
        return client, False

    shadow_news_client = getattr(client, _CLIENT_ATTR, None)
    if not callable(getattr(shadow_news_client, "news", None)):
        shadow_news_client = news_client_factory()
        if not callable(getattr(shadow_news_client, "news", None)):
            raise RuntimeError("GS549 shadow news factory returned a client without news()")
        setattr(client, _CLIENT_ATTR, shadow_news_client)

    return _ShadowObserverClient(client, shadow_news_client), True


__all__ = ["AUTHORITY", "observer_client"]
