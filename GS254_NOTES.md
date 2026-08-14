# GS254 runtime cutover fix

The deployed GS253 runtime showed zero eligible symbols even though the official Webull screener calls completed. The official `webull-openapi-python-sdk` screener methods return response objects whose payload is exposed by `response.json()`. The GS253 normalizer did not decode that response shape, so valid ranking responses normalized to zero rows.

GS254 decodes official response objects, walks Walter's live wrapper graph to the official SDK screener, fails closed on empty feeds, locks the official `rank_type` contract for most-active requests, and corrects Live Webull pipeline provenance to state that market-attention discovery is Webull-native with no Alpaca fallback.
