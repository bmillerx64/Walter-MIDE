# Gold Standard 228 — Flight Recorder Production Wiring

228 closes the gap between the replay foundation and production persistence.

The production contract is intentionally narrow: a completed scan is copied, its final symbol paths are enriched with immutable decision-time evidence for symbols that have final records, and the enriched scan is appended in Walter's existing JSONL format. Existing path evidence is preserved. Symbols without a final record remain legacy-compatible rather than receiving invented evidence.

No scoring, thresholds, ranking, qualification, market-state logic, alerts, or trading behavior are changed.

The isolated writer exists so the final `FlightRecorder.record_scan()` integration can be a one-boundary substitution rather than duplicating replay logic inside the recorder.
