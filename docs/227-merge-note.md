# Merge Note — 227

This PR is intentionally additive. It adds the tested Flight Recorder replay subsystem but does **not** alter `FlightRecorder.record_scan()` or Walter's live scanner path. That keeps this deployment observationally inert.

After this PR is loaded successfully, the next PR should be a very small production integration that calls the evidence adapter immediately before the existing recorder write. That separation gives Walter a clean rollback boundary.
