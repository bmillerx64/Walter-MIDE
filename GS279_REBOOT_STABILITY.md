# GS279 — Streamlit reboot/session stability

## Scope
Repair only Streamlit reboot/reconnect lifecycle state. No trading, scoring, gate, threshold, discovery, qualification, ranking, alert, execution, or evidence semantics are changed.

## Symptom
After a Streamlit reboot/redeploy the browser could remain in an initializing/spinner state until a manual page refresh. The process watchdog is authoritative for whether a scan is actually running, but transient session flags could survive a rerun/reconnect snapshot.

## Repair
When the process watchdog explicitly reports that no scan is running, `initialize_session_controls` now clears the one-shot `scan_requested` and `scan_stop_requested` flags. Persistent choices such as data mode and auto-scan preference are preserved. When a scan is actually running, transient flags are not rewritten mid-scan.

## Regression coverage
`tests/test_279_reboot_session_stability.py` verifies both the idle-reconnect repair and the active-scan preservation contract.
