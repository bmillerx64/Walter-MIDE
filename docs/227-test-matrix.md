# 227 Test Matrix

| Concern | Regression coverage |
| --- | --- |
| Valid replay | WATCH and ENTRY READY |
| Integrity | mutated SHA-protected evidence rejected |
| Hindsight | later live-record changes do not alter replay |
| Persistence | JSONL replay by scan id / latest symbol |
| Legacy | explicit replay-unavailable state |
| Read-only | replay does not mutate persisted scan payload |
| Audit | valid / invalid / legacy counts |
| Health | HEALTHY / LEGACY / FAIL |
| Export | recorder preserved with replay audit metadata |
| Contract | explicit safety guarantees and subsystem version |
