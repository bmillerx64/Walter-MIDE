# Gold Standard 230 — Evidence-Bound Replay Explanation

230 turns the immutable replay capability completed in 229 into a safe human-readable historical explanation boundary.

The new replay explanation layer accepts only integrity-verified replay output. It does not fetch current market data and does not inspect live scanner state, so a historical explanation cannot silently substitute newer facts for what Walter actually knew at decision time.

The Flight Recorder replay API now exposes explanation helpers for a specific scan/symbol and for the latest replayable occurrence of a symbol.

No discovery, scoring, thresholds, gates, qualification, ranking, market-state logic, alerts, UI decisions, or candidate behavior are changed.

Release gate: require CI green before merge. Rollback boundary: revert 230; production scanning and 229 replay persistence remain unchanged.
