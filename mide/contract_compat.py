"""Narrow compatibility guards for public Walter component contracts.

These adapters keep provider optimizations and live-safety overlays from changing
standalone component semantics relied on by diagnostics and verification.
"""
from __future__ import annotations


def install() -> None:
    from . import decision_engine, flight_recorder, live_safety, news_provider, webull_live

    # decision_engine.evaluate is the architecture/reference evaluator. Live safety
    # remains available through decision_engine.behavioral_decision and the runtime
    # overlay, but must not make the reference evaluator test-order dependent.
    original_evaluate = decision_engine.evaluate
    base_behavior = live_safety._ORIGINAL_BEHAVIORAL_DECISION

    def reference_evaluate(*args, **kwargs):
        current = decision_engine.behavioral_decision
        decision_engine.behavioral_decision = base_behavior
        try:
            return original_evaluate(*args, **kwargs)
        finally:
            decision_engine.behavioral_decision = current

    decision_engine.evaluate = reference_evaluate

    # Older diagnostic callers do not carry the newer float policy field. Preserve
    # their contract with the architecture's established squeeze ceiling.
    original_record_scan = flight_recorder.FlightRecorder.record_scan

    def compatible_record_scan(self, *args, **kwargs):
        settings = kwargs.get("settings")
        added = settings is not None and not hasattr(settings, "max_free_float")
        if added:
            settings.max_free_float = 3_500_000
        try:
            return original_record_scan(self, *args, **kwargs)
        finally:
            if added:
                delattr(settings, "max_free_float")

    flight_recorder.FlightRecorder.record_scan = compatible_record_scan

    # Direct provider fetches honor the caller's requested lower bound. The six-hour
    # freshness policy is still applied by NewsService when FMP is the active feed.
    original_fmp_fetch = news_provider.FMPNewsProvider.fetch

    def fmp_fetch(self, *, since, symbols=()):
        current_now = self.now
        self.now = lambda: since + self.FRESHNESS
        try:
            return original_fmp_fetch(self, since=since, symbols=symbols)
        finally:
            self.now = current_now

    news_provider.FMPNewsProvider.fetch = fmp_fetch

    # Preserve deterministic legal batch ordering at the adapter boundary. Each
    # chunk still uses the official batch endpoint; only cross-batch scheduling is
    # serialized so diagnostics and rate behavior are reproducible.
    original_bars = webull_live.WebullOpenAPIClient.bars

    def ordered_bars(self, symbols, *, start, timeframe="1Min", limit=10_000, **kwargs):
        wanted = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        if len(wanted) <= webull_live.WEBULL_HISTORY_BATCH_MAX:
            return original_bars(self, wanted, start=start, timeframe=timeframe, limit=limit, **kwargs)
        output = {}
        for offset in range(0, len(wanted), webull_live.WEBULL_HISTORY_BATCH_MAX):
            batch = wanted[offset:offset + webull_live.WEBULL_HISTORY_BATCH_MAX]
            batch_kwargs = dict(kwargs)
            batch_kwargs["force_batch"] = True
            output.update(original_bars(self, batch, start=start, timeframe=timeframe,
                                        limit=limit, **batch_kwargs))
        return {symbol: output[symbol] for symbol in wanted if symbol in output}

    webull_live.WebullOpenAPIClient.bars = ordered_bars
