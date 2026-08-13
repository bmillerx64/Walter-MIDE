# Flight Recorder Decision Replay

Walter's Gold Standard replay path is deliberately diagnostic-only.

## Contract

For a historical decision to be replayable, the Flight Recorder symbol path must contain `decision_time_evidence`, produced by `capture_decision_time_evidence()` at scan publication time. The evidence carries its own SHA-256 integrity digest.

`replay_recorded_symbol()` then reconstructs the decision explanation from that frozen payload only. It does not fetch current bars, snapshots, news, quotes, or scanner state. If the payload has been altered, replay fails closed. Older recorder entries that predate immutable evidence remain readable but explicitly report that replay is unavailable.

## Integration rule

The live recorder should attach immutable evidence only after the final candidate record for that scan is known and before the JSONL scan is written. This is additive observability; it must not modify the candidate record, ranking, scoring, thresholds, alerts, or trade behavior.
