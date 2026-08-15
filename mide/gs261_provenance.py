"""GS261: explicit Webull-only live evidence provenance contract.

Observability only. This module does not alter discovery, scoring, gates,
ranking, alerts, or execution.
"""
from __future__ import annotations

WEBULL_PROVIDER = "Webull OpenAPI SDK"
WEBULL_RADAR = "Webull OpenAPI SDK native radar"
FMP_NEWS = "Financial Modeling Prep"


def install() -> None:
    from . import webull_live

    cls = webull_live.LiveWebullProvider
    original_init = cls.__init__
    if getattr(original_init, "_gs261_provenance", False):
        return

    def provenance_init(self, *args, **kwargs):
        # GS258 already forbids retention/use of a legacy Alpaca universe
        # client. Reassert the runtime contract here and make the diagnostic
        # source map authoritative rather than leaving stale class-era labels.
        kwargs["universe_client"] = None
        original_init(self, *args, **kwargs)
        self._universe_client = None
        self.diagnostics["market_data_sources"] = {
            "universe_provider": WEBULL_RADAR,
            "quote_provider": WEBULL_PROVIDER,
            "bars_provider": WEBULL_PROVIDER,
            "streaming_provider": WEBULL_PROVIDER,
        }
        self.diagnostics["live_evidence_contract"] = {
            "mode": "LIVE_WEBULL",
            "discovery": WEBULL_RADAR,
            "quotes": WEBULL_PROVIDER,
            "bars": WEBULL_PROVIDER,
            "stream": WEBULL_PROVIDER,
            "fallback_market_data_allowed": False,
            "alpaca_runtime_enabled": False,
        }

    provenance_init._gs261_provenance = True
    cls.__init__ = provenance_init

    def pipeline_sources(self):
        extended = bool(getattr(self, "_extended_hours_enabled", False))
        return [
            {"Stage": "Universe / discovery", "Actual provider": WEBULL_RADAR,
             "Endpoint / operation": "Webull native gainers/losers + most-active screener pages",
             "Alpaca used": "No"},
            {"Stage": "Quote / snapshot retrieval", "Actual provider": WEBULL_PROVIDER,
             "Endpoint / operation": webull_live.SNAPSHOT_OPERATION +
                (" (extended/overnight enabled)" if extended else " (regular session)"),
             "Alpaca used": "No"},
            {"Stage": "Historical bars / VWAP / volume", "Actual provider": WEBULL_PROVIDER,
             "Endpoint / operation": "Webull stock bars + Walter local calculations",
             "Alpaca used": "No"},
            {"Stage": "Streaming quotes", "Actual provider": WEBULL_PROVIDER,
             "Endpoint / operation": f"SDK market-data stream via {webull_live.STREAM_HOST}",
             "Alpaca used": "No"},
            {"Stage": "News / catalyst", "Actual provider": FMP_NEWS,
             "Endpoint / operation": "FMP stock-news / press-release provider when credentialed",
             "Alpaca used": "No"},
            {"Stage": "Scanning / filtering", "Actual provider": "Walter local pipeline",
             "Endpoint / operation": "Local gates, scoring, ranking and filtering",
             "Alpaca used": "No"},
        ]

    pipeline_sources._gs261_provenance = True
    cls.pipeline_sources = pipeline_sources
