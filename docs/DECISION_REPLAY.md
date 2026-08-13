# Walter Decision Replay

Decision replay answers one question: **What did Walter know, and what decision state did that evidence support, at that exact scan?**

The replay path is deliberately isolated from live market retrieval. It accepts only a previously captured decision-time evidence snapshot, verifies its SHA-256 integrity digest, and reconstructs the recorded decision state and blockers from those frozen inputs.

## Guarantees

- No current quote, bar, news, or scanner data is fetched during replay.
- Evidence modified after capture fails integrity verification and is rejected.
- Replay does not alter scoring, gates, thresholds, ranking, alerts, or UI state.
- The original scan ID, timestamp, source-bar timestamp/age, decision inputs, qualification flags, trigger result, and blockers remain attributable to the historical decision.

## Replay states

`PARTICIPATION_BLOCKED`, `STRUCTURE_BLOCKED`, `ENTRY_READY`, `WATCH`, and `OBSERVE` are explanatory replay classifications. They do not replace Walter's production candidate/status vocabulary and cannot initiate a trade or alert.

This layer is the prerequisite for later Flight Recorder integration and scan-by-scan forensic replay.
