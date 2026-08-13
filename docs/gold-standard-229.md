# Gold Standard 229 — Live Flight Recorder Persistence Boundary

229 completes the production adoption prepared in 228.

`FlightRecorder.record_scan()` now delegates its final JSONL write to the replayable writer introduced in 228. That writer copies the completed scan, attaches SHA-256 protected decision-time evidence only where a final symbol record exists, persists the enriched scan, and returns exactly what was written.

This closes the last production gap: normal Walter scans now become immediately integrity-verifiable and deterministically replayable without changing discovery, scoring, thresholds, gates, qualification, ranking, market-state logic, alerts, or candidate behavior.

Legacy compatibility remains intact. Paths with no final record still persist without invented `decision_time_evidence`, and existing recorder readers continue to accept older JSONL scans.
