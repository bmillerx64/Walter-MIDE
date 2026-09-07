"""GS384: compact operator-facing diagnostic truth without changing scanner logic.

Walter accumulated useful forensic telemetry as the Webull/FMP pipeline matured, but
important operational facts became buried in long sidebar diagnostics.  GS384 keeps
all existing raw diagnostics intact and only enriches the already-rendered pipeline
source rows with concise live health summaries.

GS386 reuses this late diagnostic installer as the narrow bootstrap point for the
30-second observational recorder so the large package initializer stays untouched.
GS388 reuses the same bootstrap point for presentation-only Flight Recorder cleanup.

Safety contract:
- presentation/provenance only;
- no discovery, scoring, readiness, qualification, alert, execution, or order logic;
- 30-second bars remain explicitly observational only;
- underlying diagnostic counters are not rewritten or normalized.
"""
from __future__ import annotations

from functools import wraps
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _stream_summary(diagnostics: dict) -> tuple[str, str]:
    """Return a compact status label and detail string from existing telemetry."""
    stream = dict((diagnostics or {}).get("webull_stream") or {})
    auth = str(stream.get("authentication_status") or "pending").strip().lower()
    connection = str(stream.get("stream_connection_status") or "disconnected").strip().lower()
    subscribed = _int(stream.get("subscribed_symbols"))
    messages = max(
        _int(stream.get("messages_received")),
        _int(stream.get("tick_messages_received")),
    )
    disconnects = _int(stream.get("disconnect_count"))
    failures = stream.get("subscription_failures") or []
    if not isinstance(failures, (list, tuple, set)):
        failures = [failures] if failures else []
    latency = _number(stream.get("stream_latency_ms"))
    bars = _int(stream.get("thirty_second_bars_closed"))
    ready = _int(stream.get("thirty_second_symbols_ready"))
    authority = str(stream.get("thirty_second_authority") or "OBSERVATIONAL_ONLY")

    healthy = auth == "authenticated" and connection == "connected" and not failures
    if healthy:
        status = "HEALTHY"
    elif connection in {"pending", "connecting"} or auth == "pending":
        status = "PENDING"
    elif connection in {"bypassed", "replaced"}:
        status = connection.upper()
    else:
        status = "CAUTION"

    parts = [
        connection or "disconnected",
        f"{subscribed} symbols",
        f"{messages} ticks",
    ]
    if latency is not None:
        parts.append(f"{latency:.0f} ms")
    parts.extend(
        [
            f"{disconnects} disconnects",
            f"{len(failures)} subscription errors",
            f"{bars} closed 30s bars",
            f"{ready} 30s-ready symbols",
            authority,
        ]
    )
    return status, " • ".join(parts)


def _news_summary(diagnostics: dict) -> str:
    """Summarize the licensed catalyst feed actually used by the completed scan."""
    coverage = dict((diagnostics or {}).get("news_coverage") or {})
    articles = _int(coverage.get("articles_received"))
    requests = _int(coverage.get("requests_made"))
    failures = _int(coverage.get("provider_failures"))
    symbols = _int(coverage.get("unique_symbols_discovered"))
    if not any((articles, requests, failures, symbols)):
        return ""
    return (
        f"{articles} articles • {requests} requests • {symbols} symbols discovered • "
        f"{failures} provider failures"
    )


def enrich_pipeline_rows(provider, rows: list[dict]) -> list[dict]:
    """Add concise live health to existing provenance rows; preserve every row/field."""
    diagnostics = getattr(provider, "diagnostics", {}) or {}
    stream_status, stream_detail = _stream_summary(diagnostics)
    news_detail = _news_summary(diagnostics)

    output: list[dict] = []
    for original in rows or []:
        row = dict(original)
        stage = str(row.get("Stage") or "").strip().casefold()
        if stage == "streaming quotes":
            provider_name = str(row.get("Actual provider") or "Webull OpenAPI SDK").strip()
            row["Actual provider"] = f"{provider_name} • {stream_status}"
            row["Endpoint / operation"] = stream_detail
        elif stage in {"news", "news / catalyst"} and news_detail:
            endpoint = str(row.get("Endpoint / operation") or "").strip()
            row["Endpoint / operation"] = (
                f"{endpoint} • {news_detail}" if endpoint else news_detail
            )
        output.append(row)
    return output


def install() -> None:
    """Install compact health and later presentation/evidence-only diagnostics."""
    from . import webull_live
    from .gs386_30s_observational_recorder import install as install_gs386
    from .gs388_diagnostic_ui_pruning import install as install_gs388

    # These installers are evidence/presentation-only and intentionally bootstrap
    # here, after GS379 has installed the genuine Webull stream boundary.
    install_gs386()
    install_gs388()

    current_sources = webull_live.LiveWebullProvider.pipeline_sources
    if getattr(current_sources, "_gs384_signal_to_noise", False):
        return

    @wraps(current_sources)
    def pipeline_sources(self):
        return enrich_pipeline_rows(self, current_sources(self))

    pipeline_sources._gs384_signal_to_noise = True
    pipeline_sources._gs384_original = current_sources
    webull_live.LiveWebullProvider.pipeline_sources = pipeline_sources
