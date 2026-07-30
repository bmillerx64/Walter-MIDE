# Walter Architecture v1.0 (Target State)

**Status: authoritative and normative**

Walter has one candidate pipeline. Its stages, names, and order are immutable:

1. Universe Construction
2. Price Gate
3. Validity Gate
4. Free-Float Gate
5. Catalyst Assessment
6. Participation Assessment
7. Expansion Assessment
8. Mission Ranking and Publication

## Execution contract

Universe Construction may merge any approved discovery sources into one universe,
deduplicated by normalized symbol. It is the only stage allowed to introduce a
symbol. Every later stage executes exactly once, consumes only the preceding stage's
qualified output, and may only preserve or reduce membership. There are no caps,
side pipelines, repeated gates, silent removals, or downstream overrides.

Price limits and free-float limits are runtime policy. Price is evaluated before
Validity; Validity confirms usable data and legal and operational tradability.
A trading halt is a valid and desirable market state, never a rejection condition.
The provider's halt status and type remain attached to the candidate.

Catalyst Assessment performs exactly one retrieval-and-evaluation phase after all
three gates. It may combine approved news providers, but news is evidence only and
cannot discover a symbol. Participation then measures market response to that
catalyst. Expansion then measures technical readiness.

Mission Ranking ranks every and only Expansion-qualified candidate. It cannot add or
remove candidates. Final results must be durably persisted before they are published.
The scanner selected in the UI must dispatch to its corresponding implementation.

## Accountability

Every symbol admitted by Universe Construction has exactly one terminal outcome:
`Rejected`, `Qualified and Ranked`, or `Technical Failure`. Every rejection and
technical failure records the stage, category, and human-readable reason. Qualified
candidates retain the audit history and rank assigned at Stage 8. A stage exception
is contained as a Technical Failure for the affected candidate; it never causes the
candidate to disappear.

Existing providers, policy defaults, formulas, scoring and ranking policy, visual
presentation, and alerts remain authoritative unless their placement must change to
satisfy this execution contract.
