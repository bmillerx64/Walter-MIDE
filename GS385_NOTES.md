# GS385 — force clean Streamlit runtime rebuild

Observed deployment behavior after GS384: GitHub `main` advanced and all repository CI passed, but the deployed Streamlit Community Cloud process did not load the new merge.

GS385 intentionally changes no Walter application code and no dependency versions. It only touches the dependency manifest so Streamlit sees a deployment-significant file change and starts a fresh Python runtime, matching the previously successful GS265 recovery pattern for a stale long-lived Streamlit process.

This is deployment lifecycle only. It does not change discovery, market data, scoring, qualification, readiness, ranking, thresholds, alerts, execution, or candidate membership.
