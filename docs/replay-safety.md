# Replay Safety Invariants

1. Historical replay consumes only persisted `decision_time_evidence`.
2. Evidence integrity must verify before replay.
3. Current market data must never be substituted into historical evidence.
4. Legacy scans remain readable; replay absence is explicit rather than guessed.
5. Replay and audit modules are read-only and cannot change live candidate state.
6. Evidence attachment copies recorder paths and decision fields rather than mutating the live objects.
7. Production scoring, thresholds, ranking, alerts, and trading behavior remain outside the replay subsystem.
