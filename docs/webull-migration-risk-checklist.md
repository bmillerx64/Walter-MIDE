# Webull migration-risk checklist

## Scope

This checklist maps Walter's current Webull integration to official Webull OpenAPI operations, identifies fragile points behind intermittent failures, ranks the migration risks, and proposes a phased migration path with rollback points.

## Executive summary

- No active runtime import of an unofficial Webull package was found in this repository.
- The current production path already centers on `webull-openapi-python-sdk==2.0.16`, wrapped by Walter-owned adapters in `mide/webull_sdk.py`, `mide/webull_live.py`, and `mide/webull_native_radar.py`.
- The main migration risk is not a remaining unofficial dependency; it is the set of Walter-authored compatibility layers, response-shape assumptions, entitlement-sensitive discovery calls, and legacy operational expectations still sitting around the official SDK.
- The most fragile areas are native discovery fail-closed behavior, snapshot/history response-shape drift, invalid-symbol batch poisoning, hard-coded timeout/rate-limit behavior, and optional streaming bootstrap.

## 1) Current call map: Walter usage to official Webull OpenAPI equivalents

| Walter code path | Current call used in repo | Official equivalent | Purpose | Notes |
|---|---|---|---|---|
| `LiveWebullProvider.assets()` via `mide.webull_connection._webull_native_assets()` and `mide.webull_native_radar.fetch_native_radar()` | `screener.get_gainers_losers(rank_type="DAY_1", category="US_STOCK", ...)` | Official Stock Ranking API, `GET /market-data/stock-rank/list` | Discovery: top day gainers | Evidence: `mide/webull_native_radar.py`, `docs/webull-openapi-capability-audit.md` |
| Same path | `screener.get_most_active(rank_type="VOLUME", category="US_STOCK", ...)` | Official Stock Ranking API, `GET /market-data/stock-rank/list` | Discovery: top active / absolute volume | Evidence: `mide/webull_native_radar.py`, `docs/webull-openapi-capability-audit.md` |
| Diagnostic-only radar feed | `screener.get_gainers_losers(rank_type="MIN_5", ...)` | Official Stock Ranking API, `GET /market-data/stock-rank/list` | Five-minute movers diagnostics | Present for diagnostics, excluded from live discovery contract |
| Diagnostic-only radar feed | `screener.get_most_active(rank_type="RELATIVE_VOLUME_10D", ...)` | Official Stock Ranking API, `GET /market-data/stock-rank/list` | Relative-volume diagnostics | Present for diagnostics, excluded from live discovery contract |
| `WebullOpenAPIClient.snapshots()` -> `WebullSDKClient.stock_snapshot()` | SDK `get_snapshot()` / `get_stock_snapshot()` with `category="US_STOCK"` and up to 100 symbols | Official snapshot operation; repo documents this as snapshot support and Walter code targets `/openapi/market-data/stock/snapshot` | Quote/snapshot retrieval | Evidence: `mide/webull_sdk.py`, `mide/webull_live.py`, `docs/webull-openapi-capability-audit.md`, `docs/webull-initialization-diagnostics.md` |
| `LiveWebullProvider.bars()` via `WebullSDKClient.bars()` | SDK `get_history_bar()` | Official history-bar operation exposed by the SDK | Single-symbol historical bars for VWAP/volume evidence | Exact REST path should be re-verified against the live Webull docs during migration |
| `LiveWebullProvider.bars()` via `WebullSDKClient.batch_bars()` | SDK `get_batch_history_bar()` | Official batch history-bar operation exposed by the SDK | Batched historical bars | Exact REST path should be re-verified against the live Webull docs during migration |
| `LiveWebullProvider.ensure_stream()` -> `WebullSDKClient.stream()` | `webull.data.data_streaming_client.DataStreamingClient` | Official Webull streaming transport | Optional real-time quotes/trades | Streaming remains optional and snapshot proof happens first |

## Legacy or non-official remnants to retire or verify

| Remnant | Current status | Official replacement / action |
|---|---|---|
| Walter-authored `POST /api/market-data/streaming/token` bootstrap | Removed from runtime; documented as obsolete | Keep removed; use only official SDK streaming bootstrap (`docs/webull-initialization-diagnostics.md`) |
| Wrapper-level method-name fallbacks like `get_snapshot` vs `get_stock_snapshot` and alternate overnight args | Still present for SDK compatibility | Verify against the approved SDK/version contract and remove compatibility branches only after production parity is proven |
| Walter envelope-decoding helpers (`_plain()`, `_rows()`) | Still required | Keep until response shapes are contract-tested against the approved SDK version in production |

## 2) Known fragile points causing intermittent failures

| Risk | Rank | Why it is fragile | Evidence |
|---|---|---|---|
| Native discovery feed entitlement or availability failure | High | Discovery is fail-closed. If either required ranking feed fails or returns zero rows, Live Webull raises immediately and the universe is empty. | `mide/webull_native_radar.py`, `mide/webull_connection.py`, `docs/GS253.md`, `docs/GS253_ROLLBACK.md` |
| Snapshot/history response-shape drift across SDK versions | High | Walter must decode payloads from `.json()`, `.data`, `.result`, nested lists, and dict envelopes. Small SDK contract changes can silently break normalization. | `mide/webull_sdk.py`, `mide/webull_native_radar.py`, `GS254_NOTES.md`, `tests/test_254_response_object_json_decode.py` |
| Invalid-symbol batch poisoning | High | One unsupported or malformed symbol can trigger HTTP 417 behavior that forces recursive bisection or single-symbol fallbacks, increasing latency and partial-data risk. | `mide/webull_live.py`, `mide/webull_sdk.py`, `tests/test_webull_history_bar_rate_limit.py` |
| Hard-coded timeout values | Medium | Snapshot fetch and stream initialization use a fixed 8-second timeout. Slow entitlement checks or heavier batches can fail intermittently under variable network conditions. | `mide/webull_live.py` |
| Snapshot sparsity across repeated scans | Medium | Later snapshots may omit fields such as volume or previous close. Walter now merges continuity in snapshot-only mode, but the behavior is still vendor-fragile and mode-dependent. | `mide/webull_connection.py`, `tests/test_webull_snapshot_refresh.py`, `docs/gold-standard-audit-2026-08-12.md` |
| History-bar rate limiting | Medium | Walter enforces a global 1.05-second gap for single-symbol history calls. Under fallback conditions this can stretch latency sharply. | `mide/webull_sdk.py`, `tests/test_webull_history_bar_rate_limit.py` |
| Streaming bootstrap and subscription path | Medium | Streaming is optional, but when enabled it can time out or fail independently of REST snapshots. Operational state can therefore diverge between snapshot-only and stream-enabled runs. | `mide/webull_live.py`, `docs/webull-streaming-poc.md` |
| Method-name and parameter compatibility shims | Low | Fallbacks such as `get_snapshot` vs `get_stock_snapshot` and `overnight_required` vs `include_overnight` reduce breakage today but indicate version-sensitive integration seams. | `mide/webull_sdk.py` |

## 3) Ranked migration checklist

### High

- [ ] Lock the approved production SDK version and validate the exact response shapes Walter depends on.
- [ ] Reconfirm account/application entitlements for the required ranking feeds before each cutover phase.
- [ ] Keep discovery fail-closed, but add explicit rollout monitoring for zero-row ranking responses and feed-specific failures.
- [ ] Keep invalid-symbol filtering ahead of snapshot/history calls so one bad symbol cannot poison a larger batch.

### Medium

- [ ] Re-baseline timeouts using production latency data before widening rollout.
- [ ] Verify repeated-scan continuity in both snapshot-only and stream-enabled modes.
- [ ] Track single-symbol history fallbacks and treat sudden growth as a production regression.
- [ ] Validate stream bootstrap separately from REST readiness; do not treat stream health as proof that snapshots are healthy.

### Low

- [ ] Remove compatibility branches only after the approved SDK contract is stable in production.
- [ ] Keep diagnostic-only radar feeds out of live universe selection unless they earn separate approval.

## 4) Phased migration steps with minimal downtime and rollback points

### Phase 0 — Freeze and observe

- Freeze the current approved SDK version and credential/entitlement setup.
- Capture baseline metrics for ranking feed success, snapshot success, invalid-symbol skips, history fallback count, and stream-init failures.
- Rollback point: none needed; this is pre-cutover observation.

### Phase 1 — Shadow verification

- Run discovery, snapshots, and bars through the current official path in shadow or diagnostics mode while preserving the existing operator workflow.
- Compare feed counts, symbol counts, missing-price rates, and history fallback rates against the current baseline.
- Rollback point: disable shadow-only checks or ignore shadow output; live behavior stays unchanged.

### Phase 2 — Discovery cutover first

- Promote only the official ranking-based universe selection as the live discovery source.
- Keep snapshot retrieval, bars, and downstream scoring behavior unchanged.
- Require feed-by-feed PASS status before the market-attention universe is accepted.
- Rollback point: revert the GS253 discovery cutover if discovery becomes unavailable or materially inconsistent (`docs/GS253_ROLLBACK.md`).

### Phase 3 — Snapshot and history hardening

- Keep official snapshot and history calls live, but gate rollout success on stable decoded row counts, acceptable timeout rates, and bounded single-symbol fallbacks.
- Continue snapshot-first proof before any stream bootstrap.
- Rollback point: remain in snapshot-only mode and suppress stream enablement; if needed, revert only the hardening change set instead of the entire Webull path.

### Phase 4 — Optional streaming enablement

- Enable official streaming only after REST snapshots and history calls are stable under live load.
- Treat streaming as an additive latency/coverage improvement, not a dependency for basic scan correctness.
- Rollback point: disable streaming and continue with snapshot-only mode; this path already exists in `mide/webull_live.py`.

## 5) Minimal-downtime operational guardrails

- [ ] Cut over one layer at a time: discovery first, then snapshot/history hardening, then streaming.
- [ ] Keep snapshot-first initialization as the hard readiness gate.
- [ ] Do not restore hidden Alpaca fallback inside Live Webull; surface entitlement and contract failures directly.
- [ ] Keep release monitoring focused on zero-row ranking feeds, 417 invalid-symbol spikes, snapshot timeout rate, and stream-init error rate.
- [ ] Require an explicit rollback owner and a tested revert path before each phase.

## Bottom line

Walter is already mostly on the official Webull OpenAPI path. The migration risk now sits in the compatibility seams around that path: entitlement-sensitive ranking discovery, response normalization, batch error isolation, and optional streaming. The safest rollout is phased, snapshot-first, and rollback-friendly, with GS253 discovery revert and streaming disablement kept as the primary escape hatches.
