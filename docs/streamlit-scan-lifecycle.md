# Streamlit scan lifecycle

Streamlit retains `st.session_state` for a browser session but executes `app.py`
from top to bottom on every widget callback, timer reload, and scan completion.
Module locals (`records`, `scan_diagnostics`, and `updated`) therefore exist only
for one execution and must always be derived from the session's `ScanContext`.

## Runtime ownership

`mide.completed_scan.ScanContext` is the single session-scoped owner of:

* the selected live provider instance (including Webull's stream/cache),
* the active Walter pipeline object, and
* the last successfully completed `CompletedScan` (records, universe counts,
  warnings, diagnostics, provider evidence, and completion time).

The sidebar, Radar, Diagnostics, Replay, Trade Outcomes, Data Validation, and
What Changed read the same completed object. Compatibility key
`completed_scan` is only a pointer to that object for rolling deployments; no
result fields are copied into independent session-state containers.

## Creation and clearing audit

* The session-default loop creates only transient UI controls, the candidate
  ledger, and presentation histories when their keys do not exist.
* `scan_context()` creates a context once. It accepts a context from an older
  Python class definition so a Streamlit hot reload cannot discard it merely
  because `isinstance` identity changed.
* Live Webull creates its provider only when the context has no Webull provider;
  subsequent reruns and scans reuse it. Alpaca remains deliberately per-scan.
* `_run_live_pipeline` creates per-attempt working stage collections and one
  pipeline, then records that pipeline on the context. Those collections are
  not dashboard state.
* `get_store()` and `get_flight_recorder()` are `st.cache_resource` resources;
  they are not reconstructed by ordinary reruns. Mission and trade outcome
  stores are durable file-backed projections, not scan authorities.
* `finish_scan()` clears only request/running flags. Stop clears scheduling
  flags, not the context. Presentation histories may be updated independently,
  but cannot change the completed scan.
* A recovered exception is marked `scan_completed=False`. Publication rejects
  it and retains the previous completed scan. A successful run with an actually
  empty provider universe remains publishable and is the only scan path that
  may legitimately replace the displayed universe count with zero.

## Original failure

The final exception boundary converted every interrupted attempt into the same
five-tuple shape as a successful empty scan: empty records, zero universe, zero
prefilter, warnings, and fresh diagnostics. The scheduling layer then
unconditionally published that tuple, overwriting valid Webull evidence. At the
same time, result fields were mirrored across several mutable session keys, so
a rerun could render a mixture of newly reset aliases and the prior completed
object. Hot reload also rejected retained objects by exact class identity.

Publication is now transactional: only a completed attempt can replace the
context's completed scan, and all post-scan views resolve that one object.
