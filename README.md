# Walter MIDE v1.0
Clean Streamlit foundation preserving the v0.9.3 live SIP discovery, scoring and validation logic.

Deploy `app.py` from the repository root. Add `WEBULL_APP_KEY`,
`WEBULL_APP_SECRET`, and optionally `FMP_API_KEY` to Streamlit Secrets. Official
Webull OpenAPI rankings, snapshots, streaming quotes, and history bars provide
Walter's complete live market-data path. Webull provides no raw article feed, so
news is isolated behind an optional separately licensed provider abstraction.
Walter can optionally enrich free-float fundamentals with Financial Modeling
Prep's Shares Float endpoint; this is not a market-data dependency.

Webull credentials use this precedence: Streamlit Secrets, environment
variables, then a local `.env`. The `.env` fallback is disabled unless
`WALTER_ENV=development` (or `dev`/`local`) is explicitly set, so Streamlit
Cloud never depends on a local file. Configure `WEBULL_APP_KEY` and
`WEBULL_APP_SECRET` in Streamlit Secrets. Startup diagnostics in **System
Status** report only whether each credential is present and where it was found;
they never print credential values. Do not commit `.env` or credentials.

Choose **Live Webull** in the sidebar to keep one authenticated Webull stream
and in-memory quote cache across Streamlit reruns. No Alpaca module or client is
loaded on this path. **Diagnostics** reports authentication/connection state,
subscriptions, cache coverage, message count, last message, latency, and
subscription errors. Deployments whose approved OpenAPI application uses a
regional streaming bootstrap may set `WEBULL_STREAM_BOOTSTRAP_URL`; this value
is an endpoint, never a credential.

## Walter 2.19 — Structure Engine

Walter now ranks the charts a trader should stop and open. The Structure Score
combines a recent or held VWAP reclaim, shrinking distance to SuperTrend,
five-candle range compression, participation acceleration across 3/5/10 scans,
and a graduated float bonus. A fresh SuperTrend flip adds a 20-point event bonus.
The new **COILED** state sits between BUILDING and READY, and its alert presents
the evidence plus a capped breakout probability instead of an Early Setup score.

## Walter 2.15 — Live Opportunity Feed

The compact feed directly beneath Today's Mission narrates material changes for
Walter's primary and secondary focus symbols. It retains the latest 20 events,
newest first, and reports threshold crossings, VWAP and SuperTrend transitions,
material confidence moves, entry-window changes, extension, and removal from
Focus without changing scanner qualification, scoring, or ranking.

## Walter 2.14 — Trade Readiness Gauge

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
