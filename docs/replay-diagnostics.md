# Replay Diagnostics States

- **HEALTHY** — the scan contains immutable evidence and all recorded evidence digests verify.
- **LEGACY** — the scan predates immutable evidence; it remains readable but is not deterministically replayable.
- **FAIL** — one or more evidence payloads no longer match their recorded SHA-256 digest. Replay must not proceed for those payloads.

These states are suitable for a future Diagnostics panel because they describe recorder integrity only; they do not express trade quality or alter Walter's market-state assessment.
