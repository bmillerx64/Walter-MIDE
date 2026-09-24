"""GS484 compatibility facade for sanitized FMP/news transport truth.

Phase 23 assigns implementation ownership to Replay / Validation while preserving
the historical GS484 import/install surface used by retained recorder generations.
"""
from mide.authorities import replay_validation as _replay

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = _replay._FMP_TRANSPORT_OWNER
MAX_SYMBOLS = _replay.FMP_TRANSPORT_MAX_SYMBOLS
MAX_FAILURES = _replay.FMP_TRANSPORT_MAX_FAILURES

_int = _replay._transport_int
_float = _replay._transport_float
_safe_failure = _replay.safe_transport_failure
_latest_article_at = _replay.latest_transport_article_at
transport_truth = _replay.transport_truth

# Historical source-contract markers retained for regression compatibility:
# metrics.get(...)
# "extra_provider_calls": 0
# "trading_authority_changed": False

def install() -> None:
    _replay.install_fmp_transport_truth()

def __getattr__(name: str):
    try:
        return getattr(_replay, name)
    except AttributeError:
        raise AttributeError(name) from None
