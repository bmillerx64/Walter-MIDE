"""GS442: make the operator alignment ladder match Walter's canonical evidence.

Live validation on 2026-09-11 exposed a presentation mismatch: Walter's alignment
engine has already used the intended 30s -> 1m -> 3m confirmation ladder, but the
five-second opportunity card still rendered a stale 30s -> 1m -> 5m sequence. That
hid the 3-minute maturation evidence the operator actually uses and could make a
runner look less developed than Walter's stored evidence says it is.

GS442 changes presentation only. It reads the already-computed ``alignment_score``,
``alignment_label``, and ``timeframe_alignment`` mapping and renders exactly the
canonical 30s/1m/3m members. It does not calculate indicators, alter alignment score,
rank symbols, change qualification/readiness, create alerts, or affect execution.
"""
from __future__ import annotations

import html


ALIGNMENT_DISPLAY_TIMEFRAMES = ("30s", "1m", "3m")


def canonical_alignment_markup(record: dict) -> str:
    """Render the canonical 30s/1m/3m ranking-only alignment evidence."""
    details = record.get("timeframe_alignment") or {}
    if record.get("alignment_score") is None and not details:
        return ""

    steps = "".join(
        f"<span class='trend-step {'trend-ok' if (details.get(label) or {}).get('aligned') else 'trend-bad'}'>"
        f"{label} {'✓' if (details.get(label) or {}).get('aligned') else '✗'}</span>"
        for label in ALIGNMENT_DISPLAY_TIMEFRAMES
    )
    score = int(record.get("alignment_score", 0) or 0)
    label = html.escape(str(record.get("alignment_label") or "Countertrend"))
    return (
        f"<div class='trend-ladder'><span class='trend-condition'>Alignment {score}/3 · {label} · ranking only</span>"
        f"{steps}</div>"
    )


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_gs443() -> None:
    from .gs443_market_leader_radar_continuity import install as install_gs443

    install_gs443()


def install() -> None:
    """Replace only the final operator-facing alignment presentation helper."""
    from . import ui

    current = ui.alignment_markup
    if getattr(current, "_gs442_alignment_ladder_truth", False):
        # Warm sessions can already own the GS442 helper. Still converge the next
        # presentation layer so a deployment never leaves GS443 dormant.
        _install_gs443()
        return

    def alignment_markup(record: dict) -> str:
        return canonical_alignment_markup(record)

    alignment_markup.__name__ = getattr(current, "__name__", "alignment_markup")
    alignment_markup.__module__ = getattr(current, "__module__", ui.__name__)
    alignment_markup.__doc__ = canonical_alignment_markup.__doc__
    _inherit(alignment_markup, current)
    alignment_markup._gs442_alignment_ladder_truth = True
    alignment_markup._gs442_original = current
    ui.alignment_markup = alignment_markup
    _install_gs443()
