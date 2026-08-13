# Decision Replay safety boundary

Decision replay is forensic infrastructure, not a second decision engine. A replay result must never be used as a live-data substitute, must never refresh evidence from present market state, and must never directly cause an order, alert, candidate promotion, or ranking change. Integrity failure is fail-closed: the replay is rejected rather than repaired from newer data.
