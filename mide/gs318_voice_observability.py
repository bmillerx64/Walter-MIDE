"""GS318: voice request observability helpers.

Presentation/diagnostic only. This module does not change discovery, ranking,
qualification, readiness, thresholds, or execution.
"""
from __future__ import annotations

from datetime import datetime, timezone


VOICE_REQUEST_COUNT_KEY = "_walter_voice_request_count"
VOICE_LAST_PHRASE_KEY = "_walter_voice_last_requested_phrase"
VOICE_LAST_VOICE_KEY = "_walter_voice_last_requested_voice"
VOICE_LAST_REQUEST_AT_KEY = "_walter_voice_last_requested_at"


def record_voice_request(session_state, *, phrase: str, voice_name: str = "") -> dict[str, object]:
    """Record one server-side request handed to the browser speech component."""
    count = int(session_state.get(VOICE_REQUEST_COUNT_KEY, 0)) + 1
    requested_at = datetime.now(timezone.utc).isoformat()
    session_state[VOICE_REQUEST_COUNT_KEY] = count
    session_state[VOICE_LAST_PHRASE_KEY] = str(phrase)
    session_state[VOICE_LAST_VOICE_KEY] = str(voice_name or "")
    session_state[VOICE_LAST_REQUEST_AT_KEY] = requested_at
    return {
        "count": count,
        "phrase": str(phrase),
        "voice": str(voice_name or ""),
        "requested_at": requested_at,
    }


def voice_request_snapshot(session_state) -> dict[str, object]:
    """Return the latest voice transport request without mutating session state."""
    return {
        "count": int(session_state.get(VOICE_REQUEST_COUNT_KEY, 0)),
        "phrase": str(session_state.get(VOICE_LAST_PHRASE_KEY, "") or ""),
        "voice": str(session_state.get(VOICE_LAST_VOICE_KEY, "") or ""),
        "requested_at": str(session_state.get(VOICE_LAST_REQUEST_AT_KEY, "") or ""),
    }
