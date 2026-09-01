# GS346 — Finalization acceptance lock

September 1 marks the transition from feature accumulation to convergence.

This PR adds regression-only acceptance locks for the live behaviors established during the August 31 / September 1 sessions. It intentionally makes no production changes.

Locked expectations:

- Walter discovery keeps all four native Webull attention feeds: day gainers, five-minute movers, absolute volume, and relative volume.
- A below-VWAP attention name such as the observed CPOP case cannot become an entry-oriented `LOOK NOW`; it remains DEVELOPING until VWAP is reclaimed.
- A durable RDAC-style runner can be recognized as a persistent leader after repeated top-10 native leadership, constructive above-VWAP / bullish-SuperTrend structure, strengthening price-volume evidence, and a constructive post-halt resumption.
- A symbol that is currently halted is never promoted as a leader.

Finalization rule after GS346:

Do not add new trading or presentation behavior merely because one ticker behaved differently. New production changes require a reproducible live defect against one of the established contracts: discovery completeness, VWAP safety, leader persistence, scan stability, or verified provider connectivity.

The purpose is to stop Walter from becoming an endless patch stack and move development into an evidence-driven stabilization phase.
