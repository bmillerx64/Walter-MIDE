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


## Phase 3: canonical Entry Authority ownership

The first meaning-bearing migration moves the GS528 Entry Ready vocabulary into
`mide.authorities.entry_authority`.

The behavior is unchanged:

- ENTRY READY still means only `qualified_for_entry is True`;
- near-ready records remain SETTING UP with exact blockers;
- no qualification predicate or threshold moves in this phase; and
- the existing Opportunity State binding marker/order remains compatible.

`mide.gs528_canonical_entry_ready` is retained as a compatibility shim so historical
imports and installer paths do not break, but it no longer owns entry meaning.  New
Walter Next code must import canonical Entry Ready behavior from Entry Authority.


## Phase 4: base Thesis / State ownership

Walter's base Opportunity State interpretation now lives in
`mide.authorities.thesis_state`.  GS310 retains its historical UI/install surface and
re-exports the authoritative base function so the existing wrapper chain can remain
intact while later state refinements are migrated individually.

The authority exposes two deliberately different entry points:

- `base_opportunity_state` is the single base evidence-to-thesis interpretation.
- `opportunity_state` resolves the current outer GS310 compatibility callable so
  Walter Next still receives every validated legacy refinement until it is absorbed.

No later LOOK NOW, reclaim/retest, freshness, maturation, anti-chase, ranking, or Entry
Authority wrapper is removed in this phase.  Existing parity locks must remain green.


## Phase 5: numeric VWAP truth ownership

The GS468 numeric price/VWAP reconciliation rule now lives in
`mide.authorities.thesis_state`.  This preserves the established invariant that
contradictory current numeric evidence cannot allow LOOK NOW or WATCH FOR ENTRY while
price is actually below VWAP.

`mide.gs468_vwap_truth_veto` remains only as a compatibility shim at the historical
installer position.  The rule still uses already-computed snapshot and 1m evidence,
performs zero additional market-data requests, and changes no scoring, qualification,
Entry Authority, indicator formula, threshold, alert, execution, or order behavior.


## Phase 6: LOOK NOW semantic ownership

The GS467 standalone-1m ignition adjudicator now lives in
`mide.authorities.thesis_state`.

The preserved rule is narrow: a legacy 1m VWAP/SuperTrend ignition cannot own LOOK NOW
by itself. It remains DEVELOPING/EARLY WATCH unless stronger bottom-up structure is
already present through the established GS460 compression evidence or GS462 JET-FUEL
path. Fresh event/news attention and specific structural LOOK NOW paths remain
untouched.

`mide.gs467_look_now_semantic_consolidation` remains only as a compatibility shim at
its historical installer position. No thresholds, qualification, Entry Authority,
provider requests, indicators, alerts, execution, or orders change.


## Phase 7: freshness and extension ownership

Three related late-state wrappers are consolidated into
`mide.authorities.thesis_state` as one coherent family:

- GS474 compression-owned LOOK NOW freshness expiry;
- GS525 five-minute 30s attention freshness / late-continuation context; and
- GS526 3m-SuperTrend stretch adjudication.

The historical GS modules remain compatibility shims at their original install
positions, preserving wrapper order while removing their ownership of meaning.

The existing thresholds are unchanged: five minutes for 30s attention freshness and
5% maximum 3m-ST gap for an ordinary DEVELOPING setup absent a fresh higher-timeframe
maturation event. No discovery, provider calls, indicator formulas, scoring, ranking,
qualification, Entry Authority, alerts, execution, or orders change.


## Phase 8: 3m retest truth, memory, and discipline

The 3-minute SuperTrend retest family is split across the correct authorities instead
of remaining a cross-wrapped GS chain:

- **Market Evidence** owns current 3m-ST truth, held-retest reconstruction from
  already-captured session bars, and bounded retest memory.
- **Thesis / State** owns the trader-facing guardrail, thesis-vs-trigger repair
  sequence, and the explicit THESIS VALIDATED / TRIGGER NOT EARNED presentation.
- **Entry Authority** remains unchanged and is still the only component that can grant
  executable Entry Ready.

GS493, GS514, and GS515 remain compatibility facades at their historical install
positions so runtime ordering stays stable while ownership moves out of numbered
patches. No new market-data request, threshold, indicator formula, qualification,
ranking, readiness, alert, execution, or order behavior is introduced.
