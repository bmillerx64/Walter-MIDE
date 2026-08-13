# Gold Standard 232 — Immutable Calibration Records

GS 232 converts the forward-outcome primitive from GS 231 into a safe calibration dataset boundary.

A calibration record now joins exactly one integrity-verified decision-time evidence snapshot to exactly one strictly-forward outcome label. The join is rejected if scan ID, symbol, decision timestamp, or evidence SHA-256 do not match. The completed calibration record receives its own SHA-256 digest so later mutation is detectable.

Decision-time predictors are copied into the calibration record; future outcome facts remain in a separate outcome section. Neither object is allowed to mutate the source evidence or outcome supplied by the caller.

GS 232 also adds descriptive fixed-horizon aggregation. Verified records may be summarized by horizon with observation count, average/median MFE, MAE, end-of-horizon return, positive end-return rate, and average time to MFE. Mutated records are rejected instead of silently entering the sample.

This module has no policy authority. It does not fetch market data, choose thresholds, change weights, retrain scores, alter discovery, qualification, ranking, alerts, or entry state. Its only job is to make Walter's later empirical calibration reproducible and auditable.

Release gate: require CI green before merge. Rollback boundary: revert GS 232; GS 231 forward measurement and Walter production scanning remain unchanged.
