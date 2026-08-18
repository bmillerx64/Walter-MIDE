# Walter-MIDE Agent Policy

These repository guardrails make Walter's operating contract enforceable by default.

- `main` is the source of truth unless a task explicitly names another branch.
- Keep Walter fail-closed: do not loosen trading, scoring, threshold, qualification, or discovery logic to increase candidates.
- Live Webull mode must remain Webull-only; never silently substitute Alpaca when Webull fails.
- Preserve scan-trust semantics in `mide/data_integrity.py`, including HEALTHY SCAN, VALID EMPTY PASS, DEGRADED DATA, PROVIDER/PIPELINE FAILURE, and AWAITING SCAN behavior.
- Preserve completed-scan atomicity in `mide/completed_scan.py`; reruns must not replace a coherent completed scan with partial or empty transient state.
- Preserve Flight Recorder auditability and replayability, including replayable scan persistence and explainable symbol-level evidence.
- Never expose `WEBULL_APP_KEY` or `WEBULL_APP_SECRET` in code, logs, docs, tests, screenshots, or PR text.
- `runtime.txt` is the runtime authority and must remain `python-3.13` unless a PR is an explicit runtime migration.
- Keep dependency pins stable unless a task explicitly requires a change; `webull-openapi-python-sdk` upgrades require explicit approval.

See `.github/pull_request_template.md` for the required author checklist and `.github/workflows/policy-guardrails.yml` for the automated enforcement job.
