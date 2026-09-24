"""GS545: warm-deploy-safe facade for Webull stream-session takeover.

Market Evidence owns the stable MQTT session identity and retained-provider factory
rebind. This compatibility module is called from the hard live-provider boundary
before any scan can open a Webull TICK stream.

No connection is opened here and no trading authority changes.
"""

from __future__ import annotations


AUTHORITY = "WEBULL_CROSS_DEPLOYMENT_STREAM_SESSION_TAKEOVER"


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def install_for_provider(
    provider,
    app_key: str,
    app_secret: str,
) -> bool:
    current = getattr(
        _market(),
        "install_webull_stream_session_takeover",
        None,
    )
    if not callable(current):
        return False
    return bool(
        current(
            provider,
            app_key,
            app_secret,
        )
    )


__all__ = [
    "AUTHORITY",
    "install_for_provider",
]
