# Walter MIDE v1.0
Clean Streamlit foundation preserving the v0.9.3 live SIP discovery, scoring and validation logic.

Deploy `app.py` from the repository root. Add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `ALPACA_FEED = "sip"` to Streamlit Secrets.

## Walter 2.13 — Conviction Engine

The dashboard now answers **“Can I start preparing to buy?”** with one immediate,
color-coded recommendation for every displayed setup: **🟢 GREEN LIGHT** when all
requirements align, **🟡 GET READY** when exactly one condition remains, or
**🔴 NO TRADE** when the setup has multiple blockers or is too extended. The
recommendation uses completed scanner evidence and does not change qualification,
ranking, thresholds, or scoring.

## Walter Enhancement 2.9 — Escalation Engine

Walter adds a display-only escalation layer after every completed scan. It labels
actionable symbols **Entry Window Open**, **Watch Closely**, **Monitor**, or
**Too Extended**; shows confidence direction, a readiness checklist, and only
meaningful evidence changes from the immediately prior scan; and announces
actual escalation-state changes through the configured audible alert voice.

The escalation layer does not qualify, reject, score, or reorder candidates.
All scanner logic, thresholds, ranking, and scoring remain unchanged.

## Walter 2.0 Phase 1 workflow compatibility

Scanner V2 records expose three separate workflow decisions:
`qualified_for_watch` controls dashboard visibility, `qualified_for_entry`
controls executable Entry Ready setups, and `qualified_for_alert` controls entry
alerts. Strengthening is intentionally independent of Entry Ready VWAP geometry,
so an extended candidate remains visible with an entry blocker.

`qualified_for_ranking` is retained as an exact alias of
`qualified_for_entry`. The UI and alert helpers also retain fallbacks for legacy
records that do not yet contain the new fields. These shims are marked
`TODO Walter 2.0 Phase 2` at their call sites and should be removed after stored
records and downstream consumers have migrated.
