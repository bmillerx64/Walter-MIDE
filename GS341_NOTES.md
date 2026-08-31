# GS341 — deploy reconnect self-heal

Observed live behavior: after Streamlit deploy/reboot, the browser could remain visually stuck until a manual refresh even though the new Walter version had started.

GS341 extends the existing GS313 process-boundary guard. When an existing session reconnects to a new Python process and no scan watchdog is already running, Walter first clears stale scan/stop intent through GS313, completes ordinary session initialization, then requests exactly one clean Streamlit rerun against the already-warm process. The new process token prevents a rerun loop.

This is lifecycle-only. It does not change discovery, market data, scoring, qualification, readiness, ranking, thresholds, alerts, execution, or candidate membership.

Regression coverage verifies one-shot behavior, ordinary reruns, first-session startup, active-scan protection, and safe behavior outside an active Streamlit script context.
