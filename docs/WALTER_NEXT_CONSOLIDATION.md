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


## Phase 9: proven-leader reset / re-ignition authority split

GS477 previously mixed four responsibilities in one numbered module. Walter Next now
separates them:

- **Market Evidence** owns the existing 90-minute proven-leader memory and computes
  RESET WATCH / REIGNITION / 3M CONFIRMATION evidence from current VWAP, fast
  SuperTrend, participation, flow, mover membership, and source freshness.
- **Thesis / State** owns what that evidence means to the Opportunity State, including
  the below-VWAP no-promotion rule and LOOK NOW re-ignition explanation.
- **Presentation + Audio** owns awareness-only visible-row enrichment and the existing
  attention-only reset/re-ignition voice phrases.
- **Entry Authority** remains unchanged; leader-reset evidence cannot grant Entry Ready.

The numeric contracts are unchanged: >5% prior VWAP extension, +/-2% reset window,
90-minute memory, Participation >=20, volume acceleration >=1.0 or dollar-flow
acceleration >=1.25, and <=5% reclaimed VWAP distance for re-ignition.

Because GS477's audio installer causes Presentation + Audio to load during startup,
that authority's legacy UI delegates are now dynamic rather than frozen imports. This
prevents consolidation from bypassing later validated UI wrappers.


## Phase 10: authority hot-reload safety

The six-component architecture must not freeze replaceable legacy callables merely
because an authority module happened to import during package startup or a Streamlit
warm rerun.

This phase makes the remaining facade-style calls in **Discovery + News**,
**Entry Authority**, and **Replay / Validation** resolve their current validated
implementation at call time. Stable provider/recorder/store classes remain direct
imports.

Together with the dynamic delegates already added to Market Evidence and
Presentation + Audio, this removes a class of stale-reference hazards where a later
compatibility installer could correctly replace a legacy function while an authority
continued calling an older captured copy.

No strategy semantics, thresholds, provider requests, indicator formulas, scoring,
ranking, qualification, Entry Ready meaning, alerts, execution, or orders change.


## Phase 11: maturation audio ownership

The GS492/GS512 audio cluster now belongs to **Presentation + Audio**.

Presentation + Audio owns the existing RUNNER BUILDING / RUNNER DETECTED transition
truth, phrase construction, audio-priority wrapper, and the Architecture-v1 gate
fallback used by attention audio. GS492 and GS512 remain compatibility facades at
their historical install positions.

The GS512 activation order is preserved deliberately: maturation audio begins with the
historical direct gate dictionaries, and only the GS512 install point switches audio
to the Architecture-v1 audit fallback. This preserves startup/order parity rather than
silently enabling the bridge earlier.

The established 180-second fresh-3m window, >5% VWAP anti-chase wording, gate
requirements, chime priority, and no-entry-authority contract are unchanged.


## Phase 12: one authoritative operator-ordering owner

The historical final-card ordering stack no longer needs five nested wrappers.

**Presentation + Audio** now owns one sorter with staged activation for the exact
legacy sequence:

1. GS463 state-first attention bands;
2. GS465 state-contiguous cleanup and within-state attention tie-breaks;
3. GS497 Mission Rank precedence below Entry Ready;
4. GS517 fresh maturation-event priority; and
5. GS539 visible Participation/Expansion strength as the final primary order.

Each historical install point activates its stage at the same position in startup, but
`gs369.ordered_escalation_records` is wrapped only once. Later stages update the
authoritative wrapper's active-stage set rather than nesting another callable.

The final behavioral contract is unchanged: executable Entry Ready stays first, HALTED
stays last, P/E Strength is the final visible primary order for every other card, and
the preceding stages remain the stable tie/fallback history used when later evidence
does not distinguish records.

GS463, GS497, GS517, and GS539 are compatibility facades. GS465 still owns its separate
extreme-mover label/continuity semantics for now, but its ordering portion delegates to
the authoritative sorter.

No discovery, provider calls, market evidence, indicator formulas, scoring, Mission
Ranking values, qualification, Entry Ready authority, anti-chase state, alert truth,
execution, or orders change.


## Phase 13: extreme-mover presentation ownership

The late extraordinary-mover presentation chain is consolidated into
**Presentation + Audio**.

GS333 remains the base detector for an extraordinary current mover for now. The later
presentation corrections no longer stack independent wrappers around it:

- GS465 activates truthful extreme labels and the generic-WATCH continuity fallback;
- GS466 delegates the awareness-only stale-source-bar visibility exception; and
- GS495 activates the existing <=2% VWAP anti-chase qualifier.

GS465 creates one authoritative extreme-event wrapper. GS495 adds its anti-chase stage
to that same wrapper instead of nesting another callable. Historical install timing and
compatibility markers remain intact.

The existing contracts are unchanged: percentage move alone cannot manufacture LOOK
NOW, >5% above VWAP keeps the established DO NOT CHASE behavior, structurally earned
LOOK NOW between 2% and 5% is explicitly marked EXTENDED / WATCH RESET, halts retain
resume-first semantics, and stale-bar continuity can restore awareness only—not trade
authority.

No discovery, market-data requests, indicators, ranking, qualification, Entry Ready,
alerts, execution, or orders change.


## Phase 14: base extraordinary-mover presentation ownership

GS333 is now a compatibility facade. **Presentation + Audio** owns its original base
responsibilities:

- the +75% current-attention extraordinary-event description;
- halt / >5% VWAP / ordinary extreme label and guidance construction;
- priority selection among current extremes;
- extraordinary-event markup;
- action-first rendering; and
- maintenance/voice observability routing to the sidebar.

The selector deliberately resolves `gs333.extreme_market_event` dynamically at call
time. That preserves the historical startup contract: GS393 can replace priority
selection, GS465 can activate truthful extreme-label cleanup, and GS495 can activate
the later anti-chase qualifier without the base authority bypassing those refinements.

GS334/GS340's separate attention-only market-event lane is unchanged.

No discovery membership, provider requests, evidence calculations, qualification,
Entry Ready, alert authority, execution, or orders change.


## Phase 15: split GS393/GS439 across four authorities

GS393/GS439 previously combined four unrelated responsibilities in one numbered
module. Walter Next now separates them:

- **Market Evidence** owns primary 1m ignition truth: fresh VWAP reclaim/hold or fresh
  bullish 1m SuperTrend flip above VWAP, inside the existing +2% chase guard, with
  the existing support-evidence requirement. The 150-second flip freshness and
  2-bar reclaim freshness contracts are unchanged.
- **Thesis / State** owns the interpretation that fresh ignition may promote an
  otherwise-developing thesis to LOOK NOW, while never overriding Entry Ready,
  CHASE / WAIT, or HALTED.
- **Presentation + Audio** owns GS393/GS439's 180-second extended-extreme banner TTL
  and the rule that a DO-NOT-CHASE extreme immediately yields the top sightline to a
  workable WATCH FOR ENTRY / LOOK NOW / DEVELOPING peer.
- **Replay / Validation** owns enrichment of the GS390 validation sequence with the
  primary ignition definition while retaining literal ST-line/VWAP crossing as
  secondary maturation evidence.

The historical GS393 module remains a compatibility coordinator and invokes the
moved installers in its original order.

No provider calls, market-data requests, indicator formulas, qualification, Entry
Ready authority, execution, or orders change.


## Phase 16: market-leader continuity ownership

GS443 is now a compatibility facade. **Presentation + Audio** owns the watch-only
continuity lane for a dominant current Webull mover that is not already represented by
Mission, GS305 attention, or the single currently displayed extraordinary event.

The existing contracts are unchanged: +20% move, $250k dollar volume, and 78 market
dominance remain the established thresholds; the lane remains read-only, never plays
audio, never manufactures LOOK NOW or Entry Ready, and never changes qualification.

The historical GS442 cold/warm activation path still calls GS443's compatibility
installer at the same point.

GS334/GS340 remain untouched in this phase because their completed-scan/native-mover
evidence capture crosses a different authority boundary that will be split separately.


## Phase 17: native market-awareness evidence split

The GS334/GS340/GS377 family is now split by responsibility instead of sharing a
numbered-module cache.

**Market Evidence** owns:
- GS334 extraordinary Webull Day Gainer evidence (+75%, existing limit/order);
- GS340 high-liquidity trend evidence (+30%, 50M shares, <=$5, top-10);
- GS377 strategy-leader evidence (+15%, top-10, <=$5 current or implied prior close);
- the shared current market-awareness snapshot;
- completed-scan market-event retrieval; and
- the existing Webull assets observation wrappers.

**Presentation + Audio** owns:
- duplicate suppression against current actionable symbols;
- actionable-symbol tracking; and
- the LIVE MARKET EVENTS / ATTENTION ONLY header strip.

The historical startup sequence remains GS334 -> GS340 -> GS377. GS340 now activates
its rule inside the authoritative Market Evidence row function instead of wrapping
GS334's callable, while GS377 still observes the same already-fetched native Webull
rows after the GS334 capture wrapper completes.

No additional provider request is added. Discovery membership, gates, scores, ranking,
qualification, Entry Ready, alerts, execution, and orders remain unchanged.
