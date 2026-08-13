# Gold Standard Sequence — Replay Track

- **226** — Immutable decision-time evidence + deterministic replay primitive.
- **227** — Flight Recorder replay foundation, persistence API, integrity audit/export, and integration adapter.
- **Next** — Minimal production wiring: attach immutable evidence immediately before Flight Recorder JSONL persistence, then expose replay/audit through Diagnostics.

The sequence intentionally separates foundation from production wiring so a deployment failure cannot simultaneously alter live decision behavior and historical observability.
