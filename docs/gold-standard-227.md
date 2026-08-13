# Gold Standard Increment 227 — Flight Recorder Replay Foundation

This increment connects the immutable decision evidence introduced in the prior Gold Standard work to Walter's existing Flight Recorder architecture without changing production decision policy.

It adds:

- a read-only bridge from recorded symbol paths to deterministic replay;
- explicit failure for historical scans that predate immutable evidence;
- SHA-256 integrity enforcement during replay;
- helpers to attach immutable evidence to recorder paths without mutating live records;
- persisted JSONL replay by scan id or newest symbol occurrence;
- regression coverage proving later live-object changes cannot contaminate historical replay.

The production `FlightRecorder.record_scan()` is intentionally not modified in this increment. The adapter establishes and tests the integration contract first. The next deployment increment can make `record_scan()` call `make_paths_replayable()` immediately before persistence, keeping that production change extremely small and reversible.
