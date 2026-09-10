"""GS419: guarantee one audible heartbeat for every completed scan.

Live validation on 2026-09-10 showed GS418 correctly restored tier-1 audibility, but
Walter could still complete a scan in silence whenever no semantic watch/advance alert
was generated (for example, only DEVELOPING/CHASE-WAIT records).

GS419 adds a tone-only tier-1 registration at the final Opportunity State render
boundary. It does not alter escalation phrases or alert truth. Existing LOOK NOW tier-2
and entry-urgency tier-3 registrations still win through GS367's per-scan highest-tier
broker. Browser-side gating honors the existing Audible watch/advance alerts toggle.

Audio/presentation only. No discovery, market data, VWAP/ST, participation, expansion,
scoring, qualification, readiness, thresholds, cadence, execution, or orders change.
"""
from __future__ import annotations

from functools import wraps


_ALERT_TOGGLE_LABEL = "Audible watch/advance alerts"


def _respect_alert_toggle(markup: str) -> str:
    """Skip the heartbeat in-browser when Walter's existing audible-alert toggle is off."""
    text = str(markup or "")
    needle = "(() => {\n"
    if needle not in text:
        return text
    gate = f"""(() => {{
  // GS419: this heartbeat follows the existing Streamlit audible-alert toggle.
  try {{
    const doc = (window.parent && window.parent.document) ? window.parent.document : document;
    const controls = Array.from(doc.querySelectorAll('input[type="checkbox"], [role="switch"]'));
    let matched = false;
    let enabled = true;
    for (const control of controls) {{
      let node = control;
      for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {{
        if ((node.textContent || '').includes('{_ALERT_TOGGLE_LABEL}')) {{
          matched = true;
          if (typeof control.checked === 'boolean') enabled = control.checked;
          else enabled = String(control.getAttribute('aria-checked') || '').toLowerCase() !== 'false';
          break;
        }}
      }}
      if (matched) break;
    }}
    if (matched && !enabled) return;
  }} catch (_) {{}}
"""
    return text.replace(needle, gate, 1)


def heartbeat_markup(state) -> str:
    """Build one tier-1 broker registration for the currently completed scan."""
    from . import gs367_browser_audio_broker as broker
    from .gs366_rerun_alert_dedupe import completed_scan_token

    token = completed_scan_token(state)
    if token == "no-completed-scan":
        return ""
    return _respect_alert_toggle(broker.browser_broker_markup(token, 1))


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after GS414 at the final Opportunity State presentation boundary."""
    from . import ui

    current = ui.render_escalation_engine
    if getattr(current, "_gs419_completed_scan_heartbeat", False):
        return

    @wraps(current)
    def render_with_completed_scan_heartbeat(records: list[dict]) -> None:
        result = current(records)
        markup = heartbeat_markup(ui.st.session_state)
        if markup:
            # This tier-1 registration participates in GS367's existing 750 ms
            # highest-tier settle window. Any tier-2/3 alert from the same completed
            # scan therefore replaces it rather than stacking another sound.
            ui.st.components.v1.html(markup, height=0, scrolling=False)
        return result

    _inherit(render_with_completed_scan_heartbeat, current)
    render_with_completed_scan_heartbeat._gs419_completed_scan_heartbeat = True
    render_with_completed_scan_heartbeat._gs419_original = current
    ui.render_escalation_engine = render_with_completed_scan_heartbeat
