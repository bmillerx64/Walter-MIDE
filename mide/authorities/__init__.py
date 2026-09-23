"""Walter Next authoritative component boundaries.

These modules are the stable seams for architectural consolidation.  Phase 1 is
intentionally behavior-preserving: each authority delegates to the currently
validated implementation while callers migrate away from GS-specific and
render-time implementation imports.

Future consolidation should move meaning *into* these six components rather than
adding another wrapper layer around legacy code.
"""

COMPONENTS = (
    "discovery_news",
    "market_evidence",
    "thesis_state",
    "entry_authority",
    "presentation_audio",
    "replay_validation",
)

__all__ = ["COMPONENTS"]
