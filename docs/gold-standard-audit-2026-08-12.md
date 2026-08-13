# Walter MIDE — Gold Standard Audit

Date: 2026-08-12
Scope: current `main` after PR #222

## Executive judgment

Walter has crossed from prototype work into a production decision-support system. The next gains will not come from adding more heuristics. They will come from making the system empirically calibratable, operationally deterministic, architecturally explicit, and resistant to regressions.

The core thesis remains sound: discover unusual small-cap activity, distinguish true participation from noise, respect price/float/liquidity constraints, identify structure around VWAP/SuperTrend, and present timing separately from discovery. The largest remaining weakness is that many important thresholds and composites are still heuristic rather than calibrated against a labeled decision-time dataset.

## Gold Standard principles

1. **Decision-time evidence only.** No feature, label, replay, or metric may use information unavailable at the decision timestamp.
2. **Discovery, qualification, ranking, timing, and presentation remain separate concerns.** A presentation feature must never silently change funnel membership.
3. **One authoritative implementation per rule.** Runtime monkey patches and compatibility shims are temporary debt, not target architecture.
4. **Fail visibly, not silently.** Data-provider gaps must be represented as explicit data-quality state, not as zero-valued market evidence.
5. **Calibration beats intuition.** Threshold changes require replay/outcome evidence, not a single memorable chart.
6. **Reproducibility.** A completed scan must be replayable from captured inputs and produce the same decision record.
7. **Operational continuity.** Repeated scans must not collapse because a provider returns a sparse refresh.
8. **Conservative execution semantics.** Walter may surface opportunities aggressively, but Entry Ready must remain stricter than Watch.

## What is already strong

- The repository has broad regression coverage across discovery, architecture, Webull adapters, catalyst routing, participation, dashboard semantics, entry state, and repeated-scan behavior.
- Recent work correctly separated entry timing from candidate discovery and restored repeated-scan continuity after sparse Webull snapshots.
- The runtime architecture audit already distinguishes absolute participation, relative participation, acceleration, persistence, and conviction instead of treating all volume metrics as equivalent.
- Catalyst Momentum routing preserves the low-float squeeze lane while allowing a separate trusted-news route.
- Trade outcomes are downstream and do not mutate scanner thresholds automatically.

## Priority 0 — reliability and invariants

### A. CI must protect `main`

The prior workflow ran on pull requests and pushes only to a historical feature branch. A merge could therefore land on `main` without a post-merge CI run. This audit changes the push target to `main`.

### B. Production/CI Python parity

CI currently tests Python 3.13 while recent Streamlit runtime traces have shown Python 3.14. That gap matters because PyArrow/Pandas/Streamlit serialization behavior is version-sensitive. Production and CI should use the same supported Python version before Walter is considered release-stable.

### C. Eliminate import-order-dependent runtime patching

`prefilter_compat.install()` replaces `flight_recorder.prefilter_decision` at runtime. `catalyst_route.install()` replaces `WalterArchitectureV1.__init__` at runtime. Recent live regressions have already demonstrated that import order can change behavior. The target state should inject these policies explicitly when the architecture/scanner is constructed.

Do not perform this refactor as a rushed hotfix. First add contract tests that instantiate the scanner through every supported app path and prove identical wiring.

### D. Data-quality state must not masquerade as market state

Missing volume, previous close, float, news, or historical profiles should have explicit provenance and freshness. Carry-forward fields are valid only when the provider omitted a field; a fresh explicit zero must remain zero. The new repeated-scan tests should become a general provenance contract.

## Priority 1 — empirical calibration

The architecture audit states the central limitation correctly: Walter does not yet have a labeled decision-time dataset sufficient to prove which metric best predicts the user's setups.

The next major product milestone should therefore be a **Decision-Time Evidence Dataset** rather than another score.

For every scan and every candidate reaching bar analysis, persist:

- scan timestamp and market phase;
- price, VWAP relation/distance, SuperTrend state/transition;
- cumulative volume and dollar volume;
- RVOL proxy and VPI cumulative pace;
- VPI 5-minute acceleration;
- 1m/3m/5m volume acceleration;
- 1m/3m/5m dollar-flow acceleration;
- green-volume ratio and expansion quality;
- free float, float provenance, and turnover when available;
- catalyst headline/source/age/materiality when available;
- discovery/qualification/ranking/entry-state decisions and reasons;
- forward MFE/MAE at fixed horizons computed only after the fact.

The analysis layer can then evaluate precision, recall, false-positive rate, median MFE, median MAE, and time-to-MFE by setup family and market phase.

## Priority 2 — simplify overlapping scoring

Walter currently carries several overlapping concepts: Participation Score, Participation Surge, VPI, windowed acceleration, legacy Conviction, dynamic Conviction, Opportunity, Structure, and entry state.

The target trader-facing hierarchy should be simpler:

1. **Opportunity** — should this chart be opened?
2. **Buying Conviction** — is participation arriving and persisting now?
3. **Structure** — is price technically organized for a trade?
4. **Entry State** — WATCH / CORRECTING / IGNITING / RE-ENTRY CONFIRMED / EXTENDED.
5. **Risk/Data Quality** — what can invalidate confidence in the setup?

Legacy composites can remain in diagnostics until replay proves they add independent predictive value.

## Priority 3 — entry timing validation

The current entry-state classifier is logically coherent but heuristic. Examples of fixed thresholds include VWAP distance >4%, 10-minute change >12%, 1-minute acceleration >1.15 for re-acceleration, and >=1.5 for ignition. These should not be tuned from isolated examples.

Required validation:

- record every state transition at decision time;
- compare forward MFE/MAE after IGNITING and RE-ENTRY CONFIRMED;
- separately score false entry signals during CORRECTING and EXTENDED states;
- stratify by price, float, session, spread, and catalyst/no-catalyst lane;
- preserve a holdout period before accepting threshold changes.

## Priority 4 — catalyst/news architecture

News should be important but not mandatory for the non-news momentum lane. A stock can produce a valid low-float liquidity/structure event without a fresh article. Conversely, a fresh trusted material catalyst can justify keeping a larger-float mover under analysis without weakening the squeeze lane.

Gold Standard news handling should score four independent dimensions: source quality, freshness, materiality, and price/participation response. A headline alone should never be equivalent to a confirmed catalyst response.

## Priority 5 — codebase maintainability

`app.py` is now a very large orchestration/UI module. Do not refactor it for aesthetics while live behavior is still stabilizing. Once release invariants are locked, extract only clearly bounded responsibilities: scan orchestration, presentation formatting, diagnostics rendering, and session-state lifecycle.

Configuration also needs one authoritative path. `Settings.from_mapping()` currently exposes only a subset of dataclass fields to environment/mapping overrides. Either document the intentionally fixed fields or map all supported settings explicitly and test them.

## Release gate

Walter should not be called "Gold Standard" until all of the following are true:

- PR CI and post-merge `main` CI are green;
- CI runtime matches production runtime;
- a same-input replay produces the same completed-scan decision output;
- repeated scans survive sparse provider refreshes without stale data masquerading as fresh data;
- import order cannot alter scanner wiring;
- core thresholds have evidence from a labeled decision-time dataset;
- entry-state transitions have measured MFE/MAE and false-signal rates;
- the dashboard distinguishes market evidence, inferred state, and data-quality uncertainty;
- no compatibility shim can change qualification silently;
- every trading-rule change ships with a regression test and a stated hypothesis.

## Immediate next sequence

1. Protect `main` with CI. **Included in this PR.**
2. Add production/CI runtime parity and a smoke test that imports the exact Streamlit app path.
3. Add scanner-construction wiring tests that expose runtime monkey-patch/import-order dependence.
4. Build the Decision-Time Evidence Dataset and forward-outcome replay harness.
5. Only then calibrate participation, structure, catalyst, and entry thresholds.

The governing rule is simple: **Walter should become less dependent on our confidence in its logic and more dependent on evidence that its logic repeatedly works.**
