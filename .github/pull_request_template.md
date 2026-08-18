## Summary

<!-- Describe the change and why it is needed. -->

## Guardrails Checklist

- [ ] No silent provider fallback was introduced.
- [ ] Scan-trust semantics are preserved.
- [ ] Completed-scan invariants are preserved.
- [ ] Webull secrets are not logged or exposed.
- [ ] `runtime.txt` remains `python-3.13`, or this PR is an explicit runtime migration.
- [ ] Dependency pins are unchanged, or the change is justified and approved.
- [ ] Targeted tests were run and full `pytest -q` status is reported below.
- [ ] Risk and rollback notes are included below.

## Test Evidence

- Targeted tests:
- Full `pytest -q`:

## Risk / Rollback

- Risk:
- Rollback:
