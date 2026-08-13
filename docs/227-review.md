# 227 Review Focus

Review this PR as an observability subsystem, not as a strategy change. The critical questions are whether historical evidence remains immutable, whether replay fails closed on corruption, whether legacy data is treated honestly, and whether every helper remains read-only with respect to Walter's live candidate state.
