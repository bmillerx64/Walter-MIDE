# Webull initialization diagnostics

Walter no longer calls `POST /api/market-data/streaming/token`. That path was
introduced by Walter's former hand-written MQTT bootstrap, is not an operation
in the official OpenAPI SDK contract, and Webull returns HTTP 404 because no
resource exists at that URL. The old request also ran before the first snapshot,
which made an optional transport prevent the scan from proving basic REST data.

Live Webull startup now has this order:

1. Construct the official SDK client without making a Walter-authored request.
2. Install a trace around the SDK's exposed `requests` or `urllib3` transport.
3. Fetch official stock snapshots in batches of at most 100 symbols.
4. Prove that at least one requested symbol produced a usable price.
5. Leave streaming bypassed by default. When explicitly enabled, initialize it
   only through the official SDK; a streaming initialization error is fatal and
   the scan cannot continue.

At INFO level each SDK HTTP exchange prints the exact method and URL, redacted
request headers, request body, response status, redacted response headers, and
response body. Authorization, signature, application-key, token, secret, and
cookie headers are replaced with `<redacted>`. If an installed SDK does not
expose either a `session` or `pool_manager` transport, Walter emits an explicit
warning instead of claiming that HTTP tracing is active.
