# 229 Release Gate

Require pull-request CI green before merge.

Post-deploy invariant: Walter's visible candidate counts, ranking, focus targets, market confidence, alerts, scanner decisions, thresholds, and gate outcomes must remain unchanged. The intended difference is only historical observability: newly persisted production scans with final records now include integrity-verified `decision_time_evidence` and replay immediately through the existing replay API.

Rollback boundary: revert 229. Recorder JSONL remains backward compatible because the evidence field is additive and paths without final records remain unchanged.
