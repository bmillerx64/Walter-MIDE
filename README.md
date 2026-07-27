# Walter MIDE v1.0
Clean Streamlit foundation preserving the v0.9.3 live SIP discovery, scoring and validation logic.

Deploy `app.py` from the repository root. Add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `ALPACA_FEED = "sip"` to Streamlit Secrets.

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
