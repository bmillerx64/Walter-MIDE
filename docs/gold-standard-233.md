# Gold Standard 233 — Calibration Slices

GS 232 created immutable, lineage-verified calibration records. GS 233 makes those records diagnostically useful without giving historical analytics any authority over Walter's live behavior.

The new read-only slice layer compares fixed-horizon outcomes across selected decision-time dimensions, including candidate status, quality grade/score, conviction score, alignment label, trigger result, Entry Ready state, VWAP distance, and volume pace.

Every source record must pass its GS 232 integrity check. Forward horizons remain isolated. A minimum-observation gate can suppress undersized groups so tiny samples are not presented as meaningful evidence. Unsupported dimensions fail closed.

The output remains descriptive only. It does not tune thresholds, rewrite weights, change gates, rank candidates, emit alerts, or influence entry state.

This is the first layer that lets us ask empirical questions such as: Did A-grade calls actually outperform C-grade calls? Did Entry Ready calls produce better MFE/MAE than Watch calls? Which VWAP-distance or volume-pace regimes historically produced the cleanest forward behavior?

Release gate: require CI green before merge. Rollback boundary: revert GS 233; GS 232 immutable calibration records and all live scanner behavior remain unchanged.
