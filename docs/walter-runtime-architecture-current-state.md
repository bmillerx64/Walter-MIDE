# Walter Runtime Architecture (Current State)

> **Document status:** This document describes Walter's current runtime
> implementation as it exists today. It is a descriptive audit, not the target
> architecture, a design specification, or the project's constitution. The planned
> **Walter Architecture v1.0 (Target State)** will define that separate, normative
> constitution; the runtime may be aligned to it in later work.

## Change 2.2B — Participation architecture audit

## Scope and method

This is a diagnosis of the current implementation, not a scoring change. No formula,
threshold, ranking rule, state transition, or UI behavior is changed. The audit traces
the fields created in discovery through Scanner V2, workflow scoring, conviction, the
flight recorder, and the dashboard. “Predicts Blake's setups” below means architectural
fit with the setup Walter is coded to identify; the repository contains no labeled
Blake trade/outcome data, so it is **not** an empirical prediction claim.

### Measure taxonomy

- **Absolute participation** — how many shares or dollars have traded.
- **Relative participation** — activity compared with a normal or expected reference.
- **Acceleration** — recent activity compared with an earlier or time-matched rate.
- **Persistence** — expansion sustained across windows or scans.
- **Conviction** — evidence that expanding activity is directional buying rather than
  neutral liquidity or a one-bar burst.

## Participation map

| Metric / field | Purpose and formula/source | Measures | Downstream consumers | Trader meaning |
|---|---|---|---|---|
| Feed volume (`volume`) | Current cumulative share volume supplied by discovery's mover/feed record. | **Absolute participation** | Candidate discovery; legacy Participation Score; attention/dominance; session and participation gates; Scanner V2 momentum score; market phase; dynamic Conviction; UI and flight recorder | “How many shares have traded?” Useful for liquidity and scale, but not evidence that buyers are arriving now. |
| Dollar volume (`dollar_volume`) | Feed volume multiplied by the feed price in discovery. | **Absolute participation**; weak price-adjusted liquidity proxy | Discovery ordering; legacy Participation Score and risk floor; attention/dominance; session and participation gates; Scanner V2 momentum score; market phase; dynamic Conviction; UI | “How much capital has changed hands?” It distinguishes economically meaningful flow from large penny-share counts, but does not establish direction. |
| RVOL proxy (`rvol_proxy`) | `current feed volume / (previous-day volume × elapsed-session fraction)`. The elapsed fraction is approximated from current-session bar count and floored at 8%. | **Relative participation** | Legacy Participation Score; attention/dominance and tier promotion; session/participation gate; Scanner V2 momentum and transition evidence; market phase; dynamic reason copy; UI | “Is today busier than the previous day would imply by now?” It is a coarse previous-day proxy, not a multi-day time-of-day RVOL profile. |
| Legacy volume acceleration (`volume_acceleration`) | Mean volume of the latest 3 one-minute bars divided by the mean of the preceding 12 bars; returns `1.0` when history is insufficient. | **Acceleration** | Legacy Participation Score and current momentum; legacy Conviction; Scanner V2 fallbacks, transition evidence, market phase, strengthening diagnostics; dynamic Conviction; UI | “Are the last three minutes busier than the preceding twelve?” Responsive, but overlaps the newer windowed metrics and is not time-of-day normalized. |
| Green-volume ratio (`green_volume_ratio`) | Volume on the last 12 bars whose close is at/above open divided by red-bar volume; capped fallback of `3.0` when all volume is green. | **Conviction** (directional proxy) | Legacy Participation Score/current momentum; participation gate's buying-expansion check; momentum quality; tests/demo | “Is recent volume occurring more on green candles?” This is the only primitive explicitly aimed at buying direction, but candle color is not true aggressor-side order flow. |
| VPI cumulative pace (`volume_pace_ratio`) | Current regular-session cumulative volume divided by the average cumulative volume at the same minute across historical sessions. Unavailable outside regular hours or without a profile. | **Relative participation** | VPI pass; participation gate; Scanner V2 momentum score and scan-to-scan evidence; market phase; UI; diagnostics | “How fast is the stock trading versus what is normal at this exact time?” This is the cleanest time-of-day-normalized participation level. |
| VPI 5-minute acceleration (`acceleration_ratio`) | Latest five-minute volume divided by historical average five-minute volume at the same minute of day. | **Acceleration** (relative to expected); limited **persistence** over five minutes | VPI pass; participation gate fallback; Participation Surge 5-minute fallback; Scanner V2 momentum score; market phase; UI; diagnostics | “Are buyers/activity arriving now versus a normal five-minute window?” It is the most immediately legible setup-timing metric, although volume alone cannot prove buyers caused it. |
| Windowed volume acceleration (`volume_acceleration_1m`, `_3m`, `_5m`) | Each window's per-minute volume divided by the mean per-minute volume in up to 30 bars preceding the latest five bars. | **Acceleration**; the 3m/5m pair supplies **persistence** | Participation Surge; participation gate; momentum quality | “Did activity expand over one, three, and five minutes, and did it last?” The 1m value detects arrival; agreement of 3m and 5m rejects a single print. |
| Windowed dollar-flow acceleration (`dollar_flow_acceleration_1m`, `_3m`, `_5m`) | Typical price × volume per minute in each recent window divided by the pre-window baseline dollar flow per minute. | **Acceleration** in capital flow; 3m/5m supply **persistence** | Participation Surge; participation gate; UI indirectly through surge/conviction diagnostics | “Is the capital rate expanding, not just the share count?” It is price-weighted traded activity, not signed buy flow. |
| Current window dollar flow (`current_dollar_flow_1m`, `_3m`, `_5m`) | Sum of typical price × volume in each latest window. | **Absolute participation** over short windows | Participation Surge diagnostics only | “How many dollars traded in the latest window?” Diagnostic evidence; it does not affect the surge score directly beyond its acceleration ratios. |
| Baseline dollar flow/minute (`baseline_dollar_flow_per_minute`) | Mean typical price × volume over up to 30 bars before the newest five. | Reference level, not a standalone signal | Denominator for dollar-flow acceleration; Participation Surge diagnostics | “What recent dollar-flow rate counts as normal?” This should remain diagnostic. |
| Expansion quality (`expansion_quality`) | A 0–100 mix of bullish-candle frequency (34), candle body/range (24), non-declining closes (18), body growth (14), and reduced bar overlap (10) over recent bars. | **Conviction** / price-response quality | Participation Surge score and detection | “Is expanding activity producing constructive candles and progress?” It adds directional context but partly overlaps technical structure. |
| Legacy Participation Score (`participation_score`) | 0–100 sum of log-scaled share volume (22), dollar volume (16), RVOL (24), legacy acceleration (20), green-volume ratio (10), and positive price move (8). | Composite of **absolute**, **relative**, **acceleration**, and **conviction** | Participation tier; attention/historical-strength ranking; legacy status; opportunity score; dynamic Conviction (max with surge); UI/workflow | “How large and active is this mover overall?” It mixes level, change, direction, and price performance, so a score of 70 has no single trader interpretation. |
| Participation tier (`participation_tier`) | Labels Participation Score as Ordinary/Active/Strong/Exceptional/Dominant; attention ranking can overwrite the top labels using market dominance. | Categorical legacy composite | UI and attention-ranking promotion | “How exceptional is aggregate participation?” The label is not a distinct measurement and can reflect two different formulas. |
| Participation Surge (`participation_surge_score`) | 0–100 composite of best and sustained volume acceleration (30), dollar-flow acceleration (28), VWAP state (18), SuperTrend transition (16), expansion quality (16), and prior quietness (8), clamped to 100. “Detected” additionally requires score ≥72 plus volume, dollar, VWAP, fresh SuperTrend, and quality conditions. | **Acceleration**, **persistence**, and **conviction**, plus technical structure | Scanner V2 momentum score/promotion and alert events; trader-priority tie-break; Opportunity and dynamic Conviction; UI | “Did a quiet symbol transition into expanding, technically supported activity?” Despite its name, this is a setup composite, not a pure participation measure; 13/100 cannot explain which component failed. |
| Participation Gate (`participation_gate`) | Hard boolean requiring 1m and 3m volume expansion, some dollar-flow expansion, an acceleration threshold, green-volume expansion, session volume or VPI, minimum dollar volume, and RVOL or VPI. | Qualification across **absolute**, **relative**, **acceleration**, and **conviction** | Watch/entry qualification; candidate rejection; Scanner V2 state, score, reasons and alerts; UI rejection tables; flight recorder | “Is there enough measurable activity to consider the symbol?” It is a workflow decision with useful failure diagnostics, not a trader-facing metric. |
| Session volume diagnostics | Session-adjusted minimums for cumulative shares, dollars, and RVOL using fixed multipliers for pre-market/open/midday/power-hour/after-hours. | **Absolute** and **relative participation** thresholds | Participation gate; Scanner V2 momentum score and transition evidence | “Does liquidity clear the threshold expected for this session?” Fixed buckets overlap VPI but remain useful when a historical profile is unavailable. |
| Dynamic Conviction (`conviction_v2_score`) | Presentation-only 0–100 score: participation change (30), scan-to-scan dollar-volume change (20), trend (20), structure (15), catalyst (10), opportunity (5). Its participation input is the maximum of the two participation composites and change in legacy acceleration/volume. | Broad **conviction** and scan-to-scan change, not participation alone | UI explanation/history only; explicitly does not qualify, rank, promote, or trigger | “Is Walter's whole thesis strengthening?” This is broader than buying conviction and should not be relabeled as a pure participation measure. |
| Legacy Conviction (`conviction_score`) | 30 plus 6.5 per evidence check, plus up to 14 dollar-volume points, with risk penalties. Evidence includes technical, catalyst, participation, RVOL, and acceleration checks. | Broad confidence composite | Legacy statuses and UI fallback when dynamic Conviction is absent | “How many supporting conditions exist?” It is neither buying conviction nor a participation metric despite consuming participation evidence. |
| Float turnover (`float_turnover_pct`, when supplied) | Percentage of public float traded; its producer is outside this repository's discovery path. | **Relative participation** against float | Discovery reason/transition evidence and Scanner V2 momentum score | “How much of the available float has rotated?” Potentially important for small caps, but currently optional and not consistently sourced. |

## Architecture findings

### 1. Which metric best predicts the setups Blake actually trades?

**Best current architectural proxy: VPI 5-minute acceleration, confirmed by 3m/5m
windowed volume and dollar-flow expansion.** Walter's coded setup is a transition:
activity arrives now, persists longer than one print, and produces constructive price
response. The 5-minute acceleration ratio expresses the timing leg most directly and
matches the trader's natural reading of “71.4× acceleration.” The 3m/5m local windows,
dollar-flow acceleration, green-volume ratio, and expansion quality should be treated
as confirmation, not competing headline metrics.

This conclusion is a hypothesis from code semantics. A defensible predictive answer
requires a labeled dataset of Blake's traded, passed, and rejected setups with forward
outcomes. No such labels or calibration analysis exist in the repository. In
particular, a displayed `440×` or `71×` can be mathematically valid against a tiny
historical denominator while still needing liquidity and data-quality context.

### 2. Which metrics are redundant?

1. **Legacy `volume_acceleration` vs. windowed acceleration vs. VPI 5m
   acceleration.** All describe recent volume expansion with different baselines.
   Preserve them for diagnosis until validated, but only one family should lead the UI.
2. **RVOL proxy vs. VPI cumulative pace.** Both ask whether cumulative volume is ahead
   of expectation. VPI has the better historical, minute-of-day baseline in regular
   hours; RVOL remains a coarse fallback and pre/post-market aid.
3. **Feed/dollar volume repeated inside Participation Score, Participation Surge,
   Participation Gate, Opportunity, and both Conviction scores.** The same evidence is
   repeatedly repackaged, sometimes more than once in a downstream composite.
4. **Participation Score vs. Participation Surge.** Both are presented as 0–100
   participation, but the former rewards accumulated scale and the latter mixes a
   transition with VWAP/SuperTrend/quality. Their shared label hides different concepts.
5. **Green-volume ratio vs. expansion quality.** Both approximate directional buying
   from candle behavior; expansion quality is richer, while green-volume ratio is
   simpler and already gates participation.
6. **Participation tier.** It adds no information beyond its source score and may be
   overwritten by market dominance, making it semantically unstable.

### 3. Which metrics are Scanner V1 legacy artifacts?

Git history and compatibility comments identify the original scoring stack as the
legacy layer: **feed volume, dollar volume, RVOL proxy, 3-vs-12-bar
`volume_acceleration`, `green_volume_ratio`, Participation Score/tier, and legacy
Conviction Score**. They remain active compatibility inputs rather than dead code.
The clearest artifacts to demote are Participation Score/tier and the UI-visible legacy
acceleration, because they now compete with VPI, the windowed expansion family, and
Participation Surge.

**Not V1 artifacts:** VPI, its 5-minute acceleration, windowed volume/dollar-flow
acceleration, Participation Surge, Participation Gate, and dynamic Conviction were
added later for Scanner V2/Walter 2.2 behavior. “Later” does not automatically mean
“better”: Participation Surge currently bundles participation and technical setup
quality under one ambiguous label.

### 4. Which single metric should become Walter's primary trader-facing measure of buying conviction?

**Recommendation: a narrative state named `Buying Conviction`, led by VPI 5-minute
acceleration—not another numeric composite.** Its trader-facing state should eventually
be LOW / BUILDING / HIGH (after calibration), with an evidence line that retains:

- RVOL or VPI cumulative pace for relative level;
- VPI 5-minute acceleration for arrival now;
- 3m/5m volume and dollar-flow agreement for persistence;
- green-volume/expansion quality for directional confirmation; and
- absolute dollar flow for liquidity context.

If the product requires one existing number today, use **VPI 5-minute acceleration**.
Do not rename Participation Surge as buying conviction: it embeds VWAP, SuperTrend,
quietness, and candle quality, saturates at 100, and obscures the very ratios the trader
finds explanatory.

## Suggested presentation hierarchy (future work, not implemented)

1. **Primary narrative:** `Buying Conviction: HIGH / BUILDING / LOW`.
2. **Visible evidence:** `RVOL`, `pace vs expected`, `5-minute acceleration`, and
   `dollar flow expanding/not expanding`.
3. **Diagnostics:** 1m/3m/5m raw ratios, baselines, quality ingredients, gate failures,
   legacy Participation Score/tier, and Participation Surge ingredients.
4. **Separate concepts:** keep Opportunity, technical structure, catalyst, and overall
   thesis Conviction distinct from participation so Walter can explain *why* it is
   interested without circular composites.

## Validation needed before changing formulas

- Capture candidate metrics at decision time without look-ahead.
- Label Blake's actual trades plus explicit passes and missed setups.
- Compare precision/recall and forward excursion for RVOL, cumulative VPI, 5m VPI
  acceleration, sustained 3m/5m volume/dollar expansion, and the two composites.
- Stratify by session, price, float, liquidity, and denominator size; extreme ratios
  are especially sensitive to sparse historical profiles.
- Calibrate the LOW/BUILDING/HIGH narrative only after that analysis.

Until those labels exist, the safe diagnosis is to **promote the change narrative and
demote overlapping level/composite scores to diagnostics**, without changing any
formula.
