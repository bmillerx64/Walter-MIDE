"""GS546: warm-deploy-safe Webull stream retry-owner facade.

Market Evidence owns the permanent v2 session identity and no-retry SDK factory.
This unique module boundary guarantees a hot Streamlit deployment can install the
new lifecycle even if an older Market Evidence generation remains resident.

Walter's GS469 continuity remains the sole reconnect owner. No trading semantics
or market-data values change here.
"""

from __future__ import annotations

import importlib


AUTHORITY = "WALTER_WEBULL_STREAM_CONTINUITY_SOLE_RETRY_OWNER"
SESSION_ID_V2 = "ece44a916ad703b79943837bf48af3fb"


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _fallback_install(
    provider,
    app_key: str,
    app_secret: str,
) -> bool:
    if provider is None:
        return False
    snapshot_client = getattr(
        provider,
        "_snapshot_client",
        None,
    )
    sdk = getattr(
        snapshot_client,
        "sdk",
        None,
    )
    data_client = getattr(
        sdk,
        "sdk_client",
        None,
    )
    if data_client is None:
        return False

    streaming_module = importlib.import_module(
        "webull.data.data_streaming_client"
    )
    retry_module = importlib.import_module(
        "webull.core.retry.retry_policy"
    )
    no_retry_policy = getattr(
        retry_module,
        "NO_RETRY_POLICY",
        None,
    )
    if no_retry_policy is None:
        return False

    legacy_factory = getattr(
        data_client,
        "_walter_streaming_client_factory",
        None,
    )
    api_client = None
    closure = getattr(
        legacy_factory,
        "__closure__",
        None,
    )
    if closure:
        try:
            api_client = closure[0].cell_contents
        except (IndexError, ValueError):
            api_client = None

    def factory():
        _ = api_client
        return streaming_module.DataStreamingClient(
            app_key,
            app_secret,
            "us",
            SESSION_ID_V2,
            retry_policy=no_retry_policy,
        )

    data_client._walter_streaming_client_factory = factory

    diagnostics = getattr(
        provider,
        "diagnostics",
        None,
    )
    if isinstance(diagnostics, dict):
        stream = diagnostics.setdefault(
            "webull_stream",
            {},
        )
        if isinstance(stream, dict):
            stream["gs546_stream_retry_owner"] = {
                "authority": AUTHORITY,
                "stable_session_identity_v2": True,
                "sdk_internal_retry_disabled": True,
                "walter_gs469_is_sole_retry_owner": True,
                "warm_generation_fallback": True,
                "network_connection_opened_here": False,
                "rest_snapshot_history_unchanged": True,
                "genuine_webull_tick_only": True,
                "trading_authority_changed": False,
            }
    return True


def install_for_provider(
    provider,
    app_key: str,
    app_secret: str,
) -> bool:
    current = getattr(
        _market(),
        "install_webull_stream_retry_owner",
        None,
    )
    if callable(current):
        return bool(
            current(
                provider,
                app_key,
                app_secret,
            )
        )
    return _fallback_install(
        provider,
        app_key,
        app_secret,
    )


__all__ = [
    "AUTHORITY",
    "SESSION_ID_V2",
    "install_for_provider",
]
