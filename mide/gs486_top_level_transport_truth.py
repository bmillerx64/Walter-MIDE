"""GS486 compatibility facade for overwrite-proof top-level transport traces.

Replay / Validation now owns the active persistence wrapper. GS486 remains available
at the same app/startup location for hot-reload compatibility.
"""
from mide.authorities import replay_validation as _replay

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = _replay._TOP_LEVEL_TRANSPORT_OWNER

_news_transport = _replay.top_level_news_transport
_stream_transport = _replay.top_level_stream_transport

# Historical scope-lock source markers:
# truth["extra_provider_calls"] = 0
# truth["network_repair_attempted_here"] = False

def install() -> bool:
    return _replay.install_top_level_transport_truth()

def __getattr__(name: str):
    try:
        return getattr(_replay, name)
    except AttributeError:
        raise AttributeError(name) from None
