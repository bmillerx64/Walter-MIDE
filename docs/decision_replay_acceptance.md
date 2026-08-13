# Decision Replay acceptance criteria

1. Replay consumes only immutable decision-time evidence.
2. Replay rejects evidence whose integrity digest no longer matches.
3. Replay reconstructs participation-blocked, structure-blocked, watch, entry-ready, and observe explanatory states.
4. Replay preserves scan/source timestamps and exposes the exact frozen inputs used for explanation.
5. Replay performs no live data access and has no path that can trigger an alert or trade.
