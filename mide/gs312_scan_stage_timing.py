"""GS312: surface existing scan-stage timing without changing scan behavior.

Walter already records ``pipeline_timing_summary`` for every completed scan. This
module only summarizes and renders that stored telemetry. It does not start a
timer, call a provider, mutate records, or participate in discovery, scoring,
qualification, ranking, alerts, or execution.
"""
from __future__ import annotations

from typing import Iterable


def timing_snapshot(rows: Iterable[dict] | None) -> dict[str, object]:
    """Return a compact read-only summary of stored pipeline timing rows."""
    normalized: list[dict[str, object]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        stage = str(raw.get("stage") or "").strip()
        if not stage:
            continue
        try:
            elapsed_ms = max(0.0, float(raw.get("elapsed_ms") or 0.0))
        except (TypeError, ValueError):
            elapsed_ms = 0.0
        normalized.append(
            {
                "stage": stage,
                "elapsed_ms": elapsed_ms,
                "input_count": int(raw.get("input_count") or 0),
                "output_count": int(raw.get("output_count") or 0),
            }
        )

    total_row = next(
        (row for row in normalized if row["stage"] == "Total Scan"), None
    )
    stage_rows = [row for row in normalized if row["stage"] != "Total Scan"]
    slowest = max(stage_rows, key=lambda row: row["elapsed_ms"], default=None)
    total_ms = float(total_row["elapsed_ms"]) if total_row else sum(
        float(row["elapsed_ms"]) for row in stage_rows
    )
    slowest_ms = float(slowest["elapsed_ms"]) if slowest else 0.0
    share = (slowest_ms / total_ms * 100.0) if total_ms > 0 else 0.0

    detail_rows = [
        {
            "Stage": row["stage"],
            "Seconds": round(float(row["elapsed_ms"]) / 1000.0, 3),
            "Input": row["input_count"],
            "Output": row["output_count"],
            "% of total": round(
                float(row["elapsed_ms"]) / total_ms * 100.0, 1
            ) if total_ms > 0 else 0.0,
        }
        for row in sorted(
            stage_rows, key=lambda row: float(row["elapsed_ms"]), reverse=True
        )
    ]

    return {
        "measured": bool(normalized),
        "total_seconds": round(total_ms / 1000.0, 3),
        "slowest_stage": str(slowest["stage"]) if slowest else "",
        "slowest_seconds": round(slowest_ms / 1000.0, 3),
        "slowest_share_pct": round(share, 1),
        "rows": detail_rows,
    }


def timing_summary_line(snapshot: dict[str, object]) -> str:
    """Format one compact trader-facing timing sentence."""
    if not snapshot.get("measured"):
        return ""
    total = float(snapshot.get("total_seconds") or 0.0)
    stage = str(snapshot.get("slowest_stage") or "Unknown stage")
    slowest = float(snapshot.get("slowest_seconds") or 0.0)
    share = float(snapshot.get("slowest_share_pct") or 0.0)
    return (
        f"Last scan: {total:.1f}s · Slowest: {stage} "
        f"{slowest:.1f}s ({share:.0f}% of total)"
    )


def install() -> None:
    """Append timing telemetry to the Opportunity Board presentation only."""
    from . import ui

    original = ui.render_walter_mission_control
    if getattr(original, "_gs312_scan_stage_timing", False):
        return

    def render_with_scan_timing(records):
        result = original(records)
        try:
            from .completed_scan import completed_scan_for_view

            scan = completed_scan_for_view(ui.st.session_state, "GS312 scan timing")
            diagnostics = scan.diagnostics if scan else {}
            snapshot = timing_snapshot(
                diagnostics.get("pipeline_timing_summary")
                if isinstance(diagnostics, dict)
                else None
            )
            summary = timing_summary_line(snapshot)
            if summary:
                ui.st.caption(summary)
                with ui.st.expander("Scan timing", expanded=False):
                    ui.st.caption(
                        "Measurement only · stored timing from the completed scan; "
                        "this panel does not alter scanner behavior."
                    )
                    ui.st.dataframe(
                        snapshot["rows"],
                        use_container_width=True,
                        hide_index=True,
                    )
        except Exception:
            # Timing visibility must never interfere with the trading display.
            pass
        return result

    render_with_scan_timing._gs312_scan_stage_timing = True
    ui.render_walter_mission_control = render_with_scan_timing
