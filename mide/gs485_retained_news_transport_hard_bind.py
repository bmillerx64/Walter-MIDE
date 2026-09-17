"""GS485: bind GS484 transport truth into the retained GS481 recorder generation.

FR #86 proved build ca31bac273f5 was live while every persisted ``news_story_trace``
still lacked GS484's ``transport`` block.  The cause is the same warm-Streamlit split
that GS427 was built to survive: app.py imported the new GS481 module and GS484 wrapped
that module's ``_news_truth``, while the active Flight Recorder still called a retained
GS481 wrapper whose function globals belong to an older module generation.

GS485 walks the *actual active persistence wrapper graph*, finds every reachable GS481
wrapper, and replaces the ``_news_truth`` callable in that exact function-global
dictionary with the already-tested GS484 transport enrichment.  It adds no provider
request and changes no news selection, discovery, market data, indicators, scoring,
qualification, alerts, execution, or orders.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = "_walter_gs485_retained_news_transport_hard_bind_owner"


def _retained_gs481_globals() -> list[dict[str, Any]]:
    """Return unique globals dicts used by reachable retained GS481 wrappers."""
    from . import gs427_flight_recorder_latency_hard_bind as gs427
    from . import gs481_live_evidence_hard_bind as gs481

    active_globals = gs427._active_recorder_globals()
    root = active_globals.get("persist_replayable_scan")
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()

    if callable(root):
        for function in gs427._walk_functions(root):
            globals_dict = getattr(function, "__globals__", None)
            if not isinstance(globals_dict, dict):
                continue
            is_gs481 = bool(
                getattr(function, "_gs481_live_evidence_hard_bind", False)
                or globals_dict.get("__name__") == "mide.gs481_live_evidence_hard_bind"
            )
            if not is_gs481 or not callable(globals_dict.get("_news_truth")):
                continue
            if id(globals_dict) not in seen:
                seen.add(id(globals_dict))
                candidates.append(globals_dict)

    # Clean-process fallback/current generation.  Keeping this in the set makes the
    # installer correct whether Streamlit retained an old wrapper or imported fresh.
    current_globals = gs481.__dict__
    if callable(current_globals.get("_news_truth")) and id(current_globals) not in seen:
        candidates.append(current_globals)
    return candidates


def _wrap_news_truth(globals_dict: dict[str, Any]) -> bool:
    """Patch one exact GS481 function-global dictionary once."""
    from . import gs427_flight_recorder_latency_hard_bind as gs427
    from . import gs484_fmp_transport_truth as gs484

    current = globals_dict.get("_news_truth")
    if not callable(current):
        return False
    if getattr(current, _OWNER, False):
        return False

    @wraps(current)
    def retained_news_truth_with_transport(*args, **kwargs):
        truth = dict(current(*args, **kwargs) or {})
        provider, provider_source = gs427._active_provider()
        transport = gs484.transport_truth(provider)
        transport["provider_source"] = provider_source
        transport["retained_runtime_hard_bind"] = True
        truth["transport"] = transport
        truth["gs484_transport_truth"] = True
        truth["gs485_retained_transport_hard_bind"] = True
        return truth

    setattr(retained_news_truth_with_transport, _OWNER, True)
    retained_news_truth_with_transport._gs485_retained_news_transport_hard_bind = True
    retained_news_truth_with_transport._gs485_original = current
    globals_dict["_news_truth"] = retained_news_truth_with_transport
    return True


def install() -> int:
    """Patch the exact retained GS481 globals used by the active recorder graph."""
    return sum(_wrap_news_truth(globals_dict) for globals_dict in _retained_gs481_globals())
