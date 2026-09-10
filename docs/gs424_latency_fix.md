# GS424 — Warm-scan current-session history cache

Sep. 10 Flight Recorder validation after GS423 showed that warm scans still spent roughly 77 seconds from watchdog acquisition to recorder persistence, despite the convergence recorder reusing prior SuperTrend work. The remaining hot path repeatedly requested the full current-session 1-minute history for every Stage-6 candidate and relative-strength benchmark on every scan.

GS424 keeps the first request for each symbol/session unchanged as the full 04:00 ET seed. The persistent LiveWebullProvider then retains that already-retrieved history across Streamlit reruns. Warm scans request only a three-minute overlap from the oldest cached final bar and merge the returned delta by timestamp. New symbols still get the full session seed, and a new session anchor clears the cache automatically.

Scope is acquisition efficiency only. Discovery, snapshots, bar values, VWAP anchoring, SuperTrend, participation/expansion, scoring, ranking, qualification, alerting, execution, orders, and GS421-423 observational maturation semantics are unchanged.
