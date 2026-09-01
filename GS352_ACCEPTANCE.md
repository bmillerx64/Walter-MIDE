# GS352 alert transport acceptance

GS352 is presentation/transport only.

Acceptance contract:
- One explicit browser gesture arms both tone and speech for the current browser tab.
- Arm state is stored in sessionStorage under `walterVoiceArmed` and shared with the existing voice transport.
- A successful test speaks `Walter alerts ready.` and emits a short tone.
- The control never calls `speechSynthesis.cancel()` and must not disturb queued market alerts.
- No discovery, ranking, qualification, readiness, thresholds, execution, orders, or market-data behavior changes.
