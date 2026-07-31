# Webull OpenAPI capability audit

**Audit date:** 2026-07-30  
**Decision:** Webull is Walter's sole live market-data provider. Raw article news
remains an optional, separately licensed provider capability.

## Scope and source policy

This audit is limited to Webull's [official OpenAPI documentation](https://developer.webull.com/api-doc/), [official access guide](https://developer.webull.com/api-doc/prepare/api-application/), and official operation pages linked below. It intentionally excludes Webull's consumer-site/mobile calls, cookies, scraping, reverse-engineered endpoints, and unofficial libraries.

The documentation portal was not reachable from the build environment (the outbound proxy returned HTTP 403), so no live account entitlement test was possible. Endpoint availability below means “documented by Webull,” not “enabled on this particular account.” The account owner must confirm application approval and subscriptions in the Webull developer console before activation.

## Authorization, entitlement, and account prerequisites

Webull OpenAPI is not an OAuth authorization-code flow. An approved Webull OpenAPI application receives an `app_key` and `app_secret`; each HTTPS request is signed using the official signature procedure and carries the documented application key, timestamp, nonce, and signature headers. Market-data access additionally depends on the user's region, brokerage account, OpenAPI application approval, and the applicable exchange data subscription. Commercial use, display, or redistribution requires Webull's written approval and the appropriate market-data agreements; possession of retail quotes does not itself grant redistribution rights.

Trading operations require an eligible, funded Webull brokerage account connected to the approved application, the relevant trading permission for the security/product, and successful account authentication. This PR does **not** place orders.

## Capability matrix

| Requested capability | Official result | Official operation / endpoint | Requirements and limits |
|---|---|---|---|
| Raw ticker-level news articles | **Not supported** | None in the official OpenAPI catalog | The catalog exposes News Summary, not an article-feed operation. Consumer-app article traffic is out of scope. |
| Headlines and article timestamps | **Not supported** | None | News Summary does not promise an article array, headline field, publication timestamp, or article identifier. |
| Publisher/source names | **Not supported** | None | News Summary does not expose per-article publisher attribution. |
| Symbols associated with each article | **Not supported** | None | A ticker/watchlist can scope a summary request, but that is not an article-to-symbol association. |
| Watchlist news summaries | **Supported (summary only)** | [News Summary](https://developer.webull.com/api-doc/market-data/news/news-summary/) — `GET /market-data/news/summary` | Signed OpenAPI request; approved account/application and applicable market-data entitlement. Input scopes the generated summary to the documented watchlist/tickers. Output is generated summary content and must not be treated as underlying articles. |
| Gainers and losers | **Supported** | [Stock Ranking](https://developer.webull.com/api-doc/market-data/ranking/stock-ranking/) — `GET /market-data/stock-rank/list` | Signed request and market-data entitlement. Select the documented gain/decline ranking type and market. |
| Top-active | **Supported** | [Stock Ranking](https://developer.webull.com/api-doc/market-data/ranking/stock-ranking/) — `GET /market-data/stock-rank/list` | Same operation with the documented volume/turnover ranking type. Ranking fields are discovery inputs, not news. |
| Market snapshot | **Supported** | [Snapshot](https://developer.webull.com/api-doc/market-data/quote/snapshot/) — `GET /market-data/quotes` | Signed request, instrument identifiers, and relevant real-time/delayed exchange entitlement. |
| Account access | **Supported** | [Account List](https://developer.webull.com/api-doc/account/account-management/get-account-list/) — `GET /account/list`; account balance/positions are separate official account operations | Approved OpenAPI application and eligible Webull brokerage account; account/product permissions apply. |
| Future order execution | **Supported, deliberately not implemented** | [Place Order](https://developer.webull.com/api-doc/trade/order-management/place-order/) — `POST /trade/order/place` | Eligible account, trading permission, buying power, supported order/security, signed request, and all broker risk controls. |

### News Summary finding

The official **News Summary** operation returns AI-generated summary material for its requested scope. It is not a raw-news endpoint and does not contractually return the underlying articles. In particular, Walter cannot use it to obtain stable article IDs, the complete headline/timestamp/source tuple, or lossless article-symbol tags. Treating the prose summary as articles—or extracting tickers from it—would invent provenance and violate this project's structured-metadata-only rule.

Therefore Webull cannot be `WebullNewsProvider` under the required normalized article contract. Webull may become the primary **discovery and snapshot** adapter after the account's OpenAPI and exchange entitlements are confirmed.

## Phase 2B provider review

### TipRanks Enterprise Market News API — preferred raw-news candidate

TipRanks markets data feeds/API access as an enterprise product rather than a self-serve retail API. Availability, schema, latency SLA, ticker filters, publisher/source attribution, and price are supplied during enterprise sales/onboarding; authentication details and credentials are issued under that agreement. Public consumer pages are not an API and must not be scraped.

Before implementation or activation, Walter's owner must obtain written confirmation of:

1. the Market News endpoint and production authentication scheme;
2. ticker-filtered queries and incremental update/cursor semantics;
3. stable article IDs, headline, created/updated timestamps, URL, publisher, and complete symbol tags;
4. update-latency SLA and historical lookback;
5. price, request quota, concurrent-use limits, and support terms; and
6. permission to cache, display, retain, and redistribute headlines/metadata in Walter.

Official contact: [TipRanks Enterprise](https://www.tipranks.com/enterprise). No `TipRanksNewsProvider` is activated by this PR.

### Benzinga News API — prepared second fallback

Benzinga documents a credentialed commercial news API, including ticker-filterable news data, at its [official API documentation](https://docs.benzinga.com/benzinga-apis/newsfeed-v2/news). Access uses a vendor-issued API token and a paid data agreement. Exact real-time latency, fields, quotas, caching/display rights, and redistribution rights depend on the purchased license. Walter must receive credentials and written permitted-use confirmation before activation. This PR supplies only an explicit credential-pending provider guard; it makes no Benzinga network call.

## Implementation decision

* Use Webull stock rankings for the live scan universe, Webull snapshots and
  streaming for quotes, and Webull history bars for VWAP and volume evidence.
* Do not import, instantiate, or call Alpaca from a Live Webull scan.
* Keep raw news behind `NewsProvider`. Live Webull uses an explicit unavailable
  provider because News Summary is not an article feed; TipRanks or Benzinga is
  the clearly identified remaining optional external dependency.
* Preserve every structured article-symbol association and every article per symbol.
* Never infer a ticker from ordinary headline text.
* Keep TipRanks and Benzinga inactive until credentials and permitted usage are confirmed.
* Use only official Webull operations and require application credentials and
  market-data entitlement; no unofficial substitute is acceptable.
