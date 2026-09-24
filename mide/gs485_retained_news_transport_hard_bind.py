"""GS485 compatibility facade for retained GS481 transport hard-binding.

Replay / Validation now owns the implementation. This module preserves the historical
warm-runtime install point and private helper names used by compatibility tests.
"""
from mide.authorities import replay_validation as _replay

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = _replay._RETAINED_TRANSPORT_OWNER

_retained_gs481_globals = _replay.retained_gs481_globals
_wrap_news_truth = _replay.wrap_retained_news_truth

def install() -> int:
    return _replay.install_retained_news_transport_hard_bind()

def __getattr__(name: str):
    try:
        return getattr(_replay, name)
    except AttributeError:
        raise AttributeError(name) from None
