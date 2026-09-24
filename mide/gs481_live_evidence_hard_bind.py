"""GS481 compatibility facade for live recorder evidence.

Phase 23 moves GS481's observational implementation into the authoritative
Replay / Validation component. This module remains at its historical import/install
point so retained Streamlit recorder graphs and legacy tests keep the same seams.
"""
from mide.authorities import replay_validation as _replay

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = _replay._LIVE_EVIDENCE_OWNER
MAX_FAILURES = _replay.LIVE_EVIDENCE_MAX_FAILURES
MAX_TEXT = _replay.LIVE_EVIDENCE_MAX_TEXT

_sanitize = _replay.sanitize_live_failure
_json_safe = _replay.live_json_safe
_news_truth = _replay.live_news_truth
_stream_failure_truth = _replay.stream_failure_truth
_attach_stream_failure = _replay.attach_stream_failure

def install() -> None:
    _replay.install_live_evidence_hard_bind()

def __getattr__(name: str):
    try:
        return getattr(_replay, name)
    except AttributeError:
        raise AttributeError(name) from None
