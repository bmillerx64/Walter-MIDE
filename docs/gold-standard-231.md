# Gold Standard 231 — Forward Outcome Measurement Harness

231 begins the empirical-calibration half of the Gold Standard plan.

Walter can now label an integrity-verified historical decision with forward MFE, MAE, end-of-horizon return, and time-to-MFE from caller-supplied bars. The harness accepts only bars strictly after the recorded decision timestamp and only through the requested horizon; the decision bar itself and later bars are excluded.

This is intentionally a downstream measurement primitive, not a live market-data integration. It does not fetch bars, alter immutable evidence, or feed outcomes back into discovery, scoring, qualification, ranking, alerts, or entry state.

This creates the safe foundation for fixed-horizon outcome labeling and later calibration reports without introducing look-ahead bias into Walter's live decisions.

Release gate: require CI green before merge. Rollback boundary: revert 231; production scanning and replay remain unchanged.
