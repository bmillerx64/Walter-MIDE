"""GS356: make Walter's top status tell the truth about browser/session health.

Presentation and runtime-observability only.  The prior green LIVE badge meant
"Live Webull mode selected", not "the Streamlit websocket is healthy".  That is
misleading when Streamlit itself is visibly CONNECTING.  GS356 changes the badge
semantics to session health and installs a zero-height browser watcher that keeps
running if the server websocket stalls.  It can therefore turn the Walter badge
red while the last rendered scan remains frozen on screen.

No discovery, market data, scoring, thresholds, qualification, readiness,
alerts, execution, order, or scan scheduling logic changes.
"""
from __future__ import annotations

import re
from typing import Any


_STATUS_RE = re.compile(
    r"(<div id=['\"]walter-status['\"][^>]*>)(.*?)(</div>)",
    flags=re.IGNORECASE | re.DOTALL,
)


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def _status_payload(state: Any) -> dict[str, Any]:
    """Return the server-side starting point for the browser health watcher."""
    from .gs355_runtime_truth_banner import runtime_truth_snapshot

    snapshot = runtime_truth_snapshot(state)
    server_state = str(snapshot.get("state") or "STARTING").upper()
    age = snapshot.get("scan_age_seconds")
    auto = bool(snapshot.get("auto_scan"))
    reason = str(snapshot.get("reason") or "")
    if server_state == "DEGRADED":
        text, color = "🔴 DEGRADED", "#ef4444"
    elif server_state == "STARTING":
        text, color = "🟡 STARTING", "#f59e0b"
    else:
        # This deliberately says SESSION OK, not LIVE.  Data mode is already
        # shown independently in the sidebar and market phase/header.
        text, color = "🟢 SESSION OK", "#22c55e"
    return {
        "text": text,
        "color": color,
        "server_state": server_state,
        "scan_age_seconds": 0 if age is None else max(0, int(age)),
        "auto_scan": auto,
        "reason": reason,
    }


def header_with_session_truth(markup: str, payload: dict[str, Any]) -> str:
    """Replace the old mode badge with truthful health metadata."""
    if not markup or not _STATUS_RE.search(markup):
        return markup
    reason = payload.get("reason") or ""
    # Attribute values are constrained to generated numbers/booleans/state
    # labels.  The human-readable reason remains a DOM property set by JS.
    prefix = (
        "<div id='walter-status' class='control-stat-value control-live' "
        f"data-walter-scan-age='{int(payload.get('scan_age_seconds') or 0)}' "
        f"data-walter-auto='{1 if payload.get('auto_scan') else 0}' "
        f"data-walter-server-state='{str(payload.get('server_state') or 'STARTING')}' "
        f"style='color:{payload.get('color') or '#94a3b8'}'>"
    )
    replacement = prefix + str(payload.get("text") or "🟡 STARTING") + "</div>"
    rendered = _STATUS_RE.sub(replacement, markup, count=1)
    if reason:
        # Keep the generated HTML clean; watcher receives the reason separately.
        return rendered
    return rendered


def _watcher_html(reason: str = "") -> str:
    """Return browser-resident JS that survives a stalled Streamlit websocket."""
    # repr() gives a safe JS string literal for this diagnostic-only text.
    reason_literal = repr(str(reason or ""))
    return f"""
<script>
(() => {{
  const root = window.parent;
  if (!root || !root.document) return;
  if (root.__walterSessionTruthInterval) {{
    root.clearInterval(root.__walterSessionTruthInterval);
  }}
  const serverReason = {reason_literal};

  const statusNode = () => root.document.getElementById('walter-status');
  const nativeConnecting = () => {{
    try {{
      return Array.from(root.document.querySelectorAll('div,span,p')).some(el => {{
        if (el.id === 'walter-status') return false;
        if (el.children && el.children.length) return false;
        const text = (el.textContent || '').trim().toUpperCase();
        return text === 'CONNECTING' || text === '... CONNECTING' || text === '… CONNECTING';
      }});
    }} catch (_) {{
      return false;
    }}
  }};

  const paint = (text, color, title) => {{
    const el = statusNode();
    if (!el) return;
    el.textContent = text;
    el.style.color = color;
    el.style.fontWeight = '900';
    if (title) el.title = title;
  }};

  let age = Number(statusNode()?.dataset?.walterScanAge || 0);
  const tick = () => {{
    const el = statusNode();
    if (!el) return;
    const auto = el.dataset.walterAuto === '1';
    const serverState = (el.dataset.walterServerState || 'STARTING').toUpperCase();
    age += 1;

    if (root.navigator && root.navigator.onLine === false) {{
      paint('🔴 BROWSER OFFLINE', '#ef4444', 'Browser network connection is offline.');
      return;
    }}
    if (nativeConnecting()) {{
      paint('🔴 CONNECTION LOST', '#ef4444', 'Streamlit websocket is reconnecting; displayed scan may be frozen.');
      return;
    }}
    if (auto && age > 150) {{
      paint('🔴 SCAN STALE', '#ef4444', 'No completed auto-scan has rendered for more than 150 seconds.');
      return;
    }}
    if (serverState === 'DEGRADED') {{
      paint('🔴 DEGRADED', '#ef4444', serverReason || 'Latest server-side runtime health is degraded.');
      return;
    }}
    if (serverState === 'STARTING') {{
      paint('🟡 STARTING', '#f59e0b', 'Waiting for the first completed scan.');
      return;
    }}
    paint('🟢 SESSION OK', '#22c55e', 'Browser session connected; data mode is shown separately.');
  }};

  tick();
  root.__walterSessionTruthInterval = root.setInterval(tick, 1000);
}})();
</script>
"""


def render_session_truth_watcher(reason: str = "") -> None:
    """Install the zero-height browser watcher in the current Streamlit page."""
    try:
        import streamlit.components.v1 as components

        components.html(_watcher_html(reason), height=0, scrolling=False)
    except Exception:
        return


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    current_header = ui.mission_control_header_markup
    if not getattr(current_header, "_gs356_client_session_truth", False):
        def truthful_header(*args, **kwargs):
            markup = current_header(*args, **kwargs)
            if not _in_streamlit_run():
                return markup
            try:
                import streamlit as st

                payload = _status_payload(st.session_state)
                return header_with_session_truth(markup, payload)
            except Exception:
                return markup

        _inherit(truthful_header, current_header)
        truthful_header._gs356_client_session_truth = True
        truthful_header._gs356_original = current_header
        ui.mission_control_header_markup = truthful_header

    # Render the browser watcher from two always-used operator surfaces.  Either
    # wrapper is sufficient; using both makes hot-reload/import-order drift
    # harmless.  Each watcher clears the previous interval before installing.
    for attr in ("render_walter_mission_control", "render_escalation_engine"):
        current = getattr(ui, attr)
        if getattr(current, "_gs356_client_session_truth", False):
            continue

        def wrapped(records, _current=current):
            reason = ""
            try:
                import streamlit as st

                reason = _status_payload(st.session_state).get("reason") or ""
            except Exception:
                pass
            render_session_truth_watcher(reason)
            return _current(records)

        _inherit(wrapped, current)
        wrapped._gs356_client_session_truth = True
        wrapped._gs356_original = current
        setattr(ui, attr, wrapped)
