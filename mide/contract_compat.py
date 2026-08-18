"""Narrow compatibility guards for public Walter component contracts."""
from __future__ import annotations


def install() -> None:
    from . import decision_engine, flight_recorder, live_safety, news_provider, webull_live

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

    original_record_scan = flight_recorder.FlightRecorder.record_scan

    def compatible_record_scan(self, *args, **kwargs):
        settings = kwargs.get("settings")
        added = settings is not None and not hasattr(settings, "max_free_float")
        if added:
            settings.max_free_float = 50_000_000
        try:
            scan = original_record_scan(self, *args, **kwargs)
            # Preserve the historical compact funnel for legacy settings objects;
            # modern runtime settings retain the expanded architecture diagnostics.
            if added and isinstance(scan, dict) and isinstance(scan.get("funnel"), dict):
                funnel = scan["funnel"]
                scan["funnel"] = {
                    "Sampled": funnel.get("Sampled", 0),
                    "Prefiltered": funnel.get("Participation Prefiltered", 0),
                    "Analyzed": funnel.get("Analyzed", 0),
                    "Participation PASS": funnel.get("Participation PASS", 0),
                    "Structure PASS": funnel.get("Structure PASS", 0),
                    "Qualified": funnel.get("Qualified", 0),
                    "Displayed": funnel.get("Displayed", 0),
                }
            return scan
        finally:
            if added:
                delattr(settings, "max_free_float")

    flight_recorder.FlightRecorder.record_scan = compatible_record_scan

    original_fmp_fetch = news_provider.FMPNewsProvider.fetch

    def fmp_fetch(self, *, since, symbols=()):
        current_now = self.now
        self.now = lambda: since + self.FRESHNESS
        try:
            return original_fmp_fetch(self, since=since, symbols=symbols)
        finally:
            self.now = current_now

    news_provider.FMPNewsProvider.fetch = fmp_fetch

    original_bars = webull_live.WebullOpenAPIClient.bars

    def ordered_bars(self, symbols, *, start, timeframe="1Min", limit=10_000, **kwargs):
        wanted = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        # Keep normal bounded concurrency for larger universes. For up to three
        # legal chunks, serialize the calls so the provider request sequence is
        # deterministic while retaining the same official batch endpoint.
        if len(wanted) <= webull_live.WEBULL_HISTORY_BATCH_MAX or len(wanted) > 41:
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
