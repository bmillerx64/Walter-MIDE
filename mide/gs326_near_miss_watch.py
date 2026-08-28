"""GS326: preserve visibility of strong setups that narrowly miss Expansion.

This module is presentation-only. It does not change discovery, identity, float,
participation, Expansion, ranking, readiness, alerts, or execution. It reuses the
already-recorded pre-Expansion diagnostic rows so a symbol can remain visible as a
near miss without becoming a ranked candidate.
"""
from __future__ import annotations

import html
from collections.abc import Iterable, Mapping


NEAR_MISS_LIMIT = 3


def near_miss_rows(
    diagnostics: Mapping[str, object] | None,
    ranked_symbols: Iterable[str] = (),
    *,
    limit: int = NEAR_MISS_LIMIT,
) -> list[dict]:
    """Return the highest-ranked Expansion rejects, without redefining eligibility."""
    if not isinstance(diagnostics, Mapping):
        return []
    post_universe = diagnostics.get("post_universe_pipeline")
    if not isinstance(post_universe, Mapping):
        return []
    rows = post_universe.get("pre_expansion_candidates") or []
    ranked = {str(symbol or "").strip().upper() for symbol in ranked_symbols}
    output = []
    for source in rows:
        if not isinstance(source, Mapping):
            continue
        symbol = str(source.get("Symbol") or "").strip().upper()
        if not symbol or symbol in ranked:
            continue
        if str(source.get("Expansion result") or "").upper() != "REJECTED":
            continue
        row = dict(source)
        row["Symbol"] = symbol
        output.append(row)
        if len(output) >= max(0, int(limit)):
            break
    return output


def near_miss_markup(rows: Iterable[Mapping[str, object]]) -> str:
    """Render a compact watch panel that cannot be mistaken for an entry signal."""
    items = []
    for row in rows:
        symbol = html.escape(str(row.get("Symbol") or ""))
        participation = row.get("Participation score")
        expansion = row.get("Expansion score")
        reason = html.escape(str(row.get("Rejected because") or "Expansion did not qualify"))
        metrics = []
        if participation is not None:
            try:
                metrics.append(f"Participation {float(participation):.0f}")
            except (TypeError, ValueError):
                pass
        if expansion is not None:
            try:
                metrics.append(f"Expansion {float(expansion):.0f}")
            except (TypeError, ValueError):
                pass
        detail = " · ".join(metrics) or "Reached Expansion"
        items.append(
            "<div style='padding:8px 10px;border-top:1px solid #263241'>"
            f"<b style='color:#fbbf24'>{symbol}</b> "
            "<span style='color:#fca5a5;font-weight:800'>NOT ENTRY QUALIFIED</span>"
            f"<div style='color:#dbe7f4;font-size:.88rem'>{html.escape(detail)}</div>"
            f"<div style='color:#93a4b8;font-size:.80rem'>{reason}</div>"
            "</div>"
        )
    if not items:
        return ""
    return (
        "<div style='background:#0b1119;border:1px solid #76551c;border-radius:12px;"
        "margin:-6px 0 16px;padding:10px 12px'>"
        "<div style='font-size:.78rem;letter-spacing:.1em;font-weight:950;color:#fbbf24'>"
        "NEAR-MISS WATCH</div>"
        "<div style='color:#aeb9c7;font-size:.82rem;margin:4px 0 6px'>"
        "Strongest names that reached Expansion but did not qualify. Watch only; the gate remains closed."
        "</div>"
        + "".join(items)
        + "</div>"
    )


def install() -> None:
    """Append the near-miss panel to the existing Opportunity Board renderer."""
    from . import ui
    from .completed_scan import completed_scan_for_view

    current = ui.render_walter_mission_control
    if getattr(current, "_gs326_near_miss_watch", False):
        return
    original = current

    def render_walter_mission_control(records: list[dict]) -> None:
        original(records)
        completed = completed_scan_for_view(ui.st.session_state, "GS326 near-miss watch")
        if completed is None:
            return
        ranked_symbols = [record.get("symbol") for record in records or []]
        rows = near_miss_rows(completed.diagnostics, ranked_symbols)
        markup = near_miss_markup(rows)
        if markup:
            ui.st.markdown(markup, unsafe_allow_html=True)

    render_walter_mission_control._gs326_near_miss_watch = True
    render_walter_mission_control._gs326_original = original
    ui.render_walter_mission_control = render_walter_mission_control
