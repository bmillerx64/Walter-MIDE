# Walter Next architectural consolidation

## Baseline

Walter v3 is frozen at commit `b6665e177f97945991edfedfca1717051b50be14`
on `walter-v3-baseline-2026-09-23`.  Walter Next develops from
`walter-consolidation`.

The existing GS modules are **reference implementation**, not disposable history.
Consolidation must preserve learned trading behavior and prove parity before a legacy
implementation is removed.

## Six authoritative components

Walter Next has exactly six meaning-bearing component boundaries:

1. **Discovery + News** — universe discovery, native movers, catalyst/news acquisition,
   and symbol admission context.
2. **Market Evidence** — market observations and derived evidence such as VWAP,
   SuperTrend, Participation, Expansion, retests/reclaims, continuation, and timing.
3. **Thesis / State** — converts evidence into the current thesis, attention state,
   escalation/de-escalation, and mission ranking.
4. **Entry Authority** — the single canonical decision boundary for watch/alert/Entry
   Ready authority, including anti-chase and halt/session safety.
5. **Presentation + Audio** — renders authoritative state and announces it; it must not
   invent or reinterpret trading meaning.
6. **Replay / Validation** — records enough authoritative evidence/state to reproduce
   and compare live decisions without changing them.

The stable import seams live in `mide/authorities/`.

## Phase 1 rule

Phase 1 changes **architecture, not behavior**.  The authority modules are facades that
delegate directly to the existing validated implementation.  No threshold, formula,
ranking rule, qualification rule, anti-chase rule, VWAP/ST behavior, Participation,
Expansion, retest/reclaim behavior, halt safety, continuation behavior, canonical Entry
Ready behavior, presentation ordering, or audio meaning is changed.

The production app begins importing behavior through these authority seams.  Dynamic
imports that exist specifically for Streamlit hot-reload/retained-module repair may
remain temporarily until that runtime problem is consolidated separately.

## Migration rule

From this point forward:

- Do not create a new GS wrapper to change meaning in Walter Next.
- Put new consolidation work behind one of the six authority boundaries.
- Move one validated behavior at a time from a legacy implementation into its authority.
- Keep parity/regression tests before deleting or bypassing the legacy source.
- Presentation may consume authoritative meaning but may not create it.
- Entry Authority is the only place allowed to grant Entry Ready.
- Replay / Validation observes decisions; it never grants trading authority.

## First target after Phase 1

The first semantic consolidation target is the current **Thesis / State + Entry
Authority handoff**, because Opportunity State, escalation, ranking, and Entry Ready
currently span the largest number of historical wrappers.  Before moving logic, capture
parity fixtures from the frozen baseline for representative states: WAIT, DEVELOPING,
LOOK NOW, ENTRY READY, extended/anti-chase, retest/reclaim, continuation/re-ignition,
and halted/unsafe.


## Phase 2 parity harness

Before moving Thesis / State or Entry Authority logic, Walter Next freezes a small set
of representative baseline behaviors behind the authority seams.  The parity cases
cover:

- DEVELOPING for constructive but insufficient participation;
- LOOK NOW for current mover + fresh flow;
- CHASE / WAIT for extension;
- HALTED as the overriding safety state;
- WATCH FOR ENTRY for aligned current evidence;
- canonical ENTRY READY only when executable authority is true;
- false legacy Entry Ready remaining SETTING UP;
- continuation re-ignition satisfying the SuperTrend lock only inside the entry zone;
- retest-entry shadow behavior; and
- anti-chase remaining authoritative during retest evaluation.

These tests are migration locks, not new strategy specifications.  As legacy logic is
absorbed into the authority modules, the same inputs must keep producing the same
meaning unless a later, separately reviewed strategy change intentionally revises the
contract.
