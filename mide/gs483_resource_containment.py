"""GS483: historical compatibility facade for Flight Recorder resource containment.

Phase 24 moves GS483's read-side recorder containment into Walter Next's authoritative
Replay / Validation component. The historical module/import/install surface remains
available for startup order, warm Streamlit generations, and regression compatibility.

Only recorder reads are affected: bounded latest-scan tail reads, streaming scan reads,
streaming symbol history, and metadata-only resource diagnostics. Recorder writes,
on-disk evidence, downloads, replay semantics, and all trading authority remain
unchanged.
"""
from mide.authorities import replay_validation as _replay


AUTHORITY = _replay.RESOURCE_CONTAINMENT_AUTHORITY
TAIL_CHUNK_BYTES = _replay.RESOURCE_TAIL_CHUNK_BYTES
_INSTALL_GENERATION = _replay._RESOURCE_CONTAINMENT_INSTALL_GENERATION

_decode_json_line = _replay.decode_recorder_json_line
_iter_valid_scans = _replay.iter_valid_recorder_scans
bounded_latest_scan = _replay.bounded_latest_scan
streaming_scans = _replay.streaming_scans
streaming_symbol_history = _replay.streaming_symbol_history
resource_snapshot = _replay.recorder_resource_snapshot


def install() -> None:
    """Install GS483 through authoritative Replay / Validation ownership."""
    _replay.install_resource_containment()


def __getattr__(name: str):
    try:
        return getattr(_replay, name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "TAIL_CHUNK_BYTES",
    "bounded_latest_scan",
    "streaming_scans",
    "streaming_symbol_history",
    "resource_snapshot",
    "install",
]
