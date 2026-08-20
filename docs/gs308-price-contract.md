# GS308 — Authoritative price mission

Walter's low-priced momentum mission is now defined once in `mide.config` as $0.02–$5.00. The legacy root `config.py` re-exports the same `Settings` class so older imports cannot drift to a different price band.

A stale environment or Streamlit `MAX_PRICE` value may no longer expand Walter beyond $5.00. It may only narrow the configured band. This prevents higher-priced symbols such as IPST at $12.38 from entering Walter's intended candidate pipeline because of configuration drift.
