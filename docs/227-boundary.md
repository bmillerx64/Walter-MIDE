# 227 Production Boundary

No existing production source file is changed in 227. This is deliberate. The branch builds and tests the complete replay-side contract against the immutable evidence already on `main`, while leaving the currently working scanner deployment untouched.

The following increment has exactly one production responsibility: enrich each final Flight Recorder symbol path with immutable evidence immediately before persistence. UI exposure comes only after that write path is proven stable.
