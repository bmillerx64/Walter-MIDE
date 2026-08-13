# Replay Acceptance Checklist

This increment is accepted when:

- replay of valid frozen evidence returns the original WATCH / ENTRY READY / blocked state;
- any evidence mutation causes integrity verification to fail closed;
- changing a live candidate after capture cannot change its historical replay;
- persisted JSONL scans can be replayed by scan id and symbol;
- legacy scans without immutable evidence are identified, not reconstructed from hindsight;
- audit/export can quantify valid, invalid, and legacy evidence coverage;
- no existing production file is modified by this increment.
