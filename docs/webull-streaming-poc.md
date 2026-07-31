# Webull OpenAPI streaming proof of concept

## Status and safety boundary

This repository now contains an **instrumented benchmark harness behind Walter's
`MarketDataProvider` boundary**, not a claim
that an all-market Webull feed has been validated. A live answer requires an
approved Webull OpenAPI application, U.S. real-time exchange entitlements, the
official streaming bootstrap response, and a permitted symbol/instrument list.
None of those credentials are committed to Walter. Consumer cookies, scraped
endpoints, and reverse-engineered Webull protocols remain out of scope.

`AlpacaProvider` keeps the production Alpaca polling path fully functional. It
and `WebullProvider` expose quotes, trades, news, snapshots, and subscriptions
through one interface, so Walter's indicators, conviction, and alerts never
depend on either vendor. Alpaca polling has deliberately not been removed before the
replacement passes the benchmark. The safe migration is: run the proof of
concept, establish the licensed subscription ceiling, then put a Webull adapter
behind Walter's provider seam and retain polling as a rollback path.

## Running the live experiment

1. Use Webull's official SDK/API with the approved `app_key` and `app_secret` to
   authenticate and obtain the short-lived MQTT/WebSocket connection values.
2. Export the returned broker values as `WEBULL_MQTT_HOST`,
   `WEBULL_MQTT_USERNAME`, `WEBULL_MQTT_PASSWORD`, and
   `WEBULL_MQTT_CLIENT_ID`. Set `WEBULL_MQTT_PORT` when it is not 443. Set
   `WEBULL_MQTT_TOPIC_TEMPLATE` to the topic documented for the approved feed,
   with `{symbol}` where the instrument identifier belongs. Never persist the
   password/token in a results file.
3. Produce a newline-delimited file of **Webull instrument identifiers** for all
   entitled U.S. equities. The ordering should be fixed and the input file's
   checksum retained with the experimental record.
4. Run during a liquid regular-hours window:

   ```bash
   python -m mide.webull_stream_benchmark webull-us-equities.txt \
     --duration 300 --output webull-stream-results.json
   ```

One authenticated connection is grown cumulatively to 100, 500, 2,000, and all
input symbols. Each tier records message-to-handler latency, process CPU time,
peak resident memory, payload bandwidth, sequence gaps, cache coverage, and
transport/subscription failure. Sequence gaps are the only defensible dropped
message measurement; if the entitled payload has no monotonic per-symbol
sequence, the report must label dropped messages **unmeasurable**, rather than
interpreting zero as proof of no loss. Network overhead is not included in
payload bandwidth, so externally capture interface bytes when capacity planning.

## Acceptance and decision

Repeat each tier on several high-volume sessions and include reconnects and token
renewal. A tier is sustainable only when it runs for the required observation
window without broker rejection/disconnect, latency remains below the selected
SLO, memory and CPU reach a stable plateau, sequence gaps remain acceptable, and
every symbol expected to trade can update. Zero updates for an illiquid security
do not alone prove a missing subscription, so reconcile acknowledgements and
periodic official snapshots.

The maximum sustainable subscription count is the largest repeatedly passing
tier—not the largest subscribe call that returned success. Walter can claim an
entire-U.S.-equity real-time cache only if the final tier passes, the complete
universe fits the account's contractual limits, entitlements cover every venue,
and Webull permits this caching use. Until a credentialed run produces that
evidence, the report's conclusion is **undetermined**, and Walter must not switch
off its current provider.
