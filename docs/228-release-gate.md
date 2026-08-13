# 228 Release Gate

Before merging 228, require CI green. After deployment, Walter's visible candidate counts, ranking, focus targets, market confidence, alerts, and scanner decisions should remain unchanged. The only intended behavioral difference is that newly persisted Flight Recorder paths with final records become integrity-verified and deterministically replayable.

Rollback boundary: revert 228. Existing recorder JSONL remains backward compatible because `decision_time_evidence` is additive.
