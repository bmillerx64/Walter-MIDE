"""GS355: make Walter runtime/session health explicit at the operator surface.

Presentation/diagnostic only. No discovery, market-data membership, scoring,
ranking, qualification, readiness, alerts, execution, orders, or trading logic
changes. The banner distinguishes the last completed scan from browser/session
health and exposes stale-scan/provider/rerun evidence that previously remained
hidden behind a green LIVE badge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STALE_AUTO_SCAN_SECONDS = 150


def _aware_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def runtime_truth_snapshot(state, *, now: datetime | None = None) -> dict[str, Any]:
    """Return one operator-facing health snapshot from existing runtime evidence."""
    from .completed_scan import LAST_SCAN_FAILURE_KEY, completed_scan_for_view
    from .gs347_native_radar_timeout_health import runtime_health
    from .gs351_session_rerun_isolation import SUPPRESSED_RERUNS_KEY
    from .session_controls import AUTO_SCAN_KEY, SCAN_REQUESTED_KEY, SCAN_RUNNING_KEY

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    completed = completed_scan_for_view(state, "runtime health")
    completed_at = _aware_utc(getattr(completed, "completed_at", None))
    scan_age = None if completed_at is None else max(0.0, (now - completed_at).total_seconds())
    auto_scan = bool(state.get(AUTO_SCAN_KEY, False))
    scan_running = bool(state.get(SCAN_RUNNING_KEY, False))
    scan_requested = bool(state.get(SCAN_REQUESTED_KEY, False))
    native = runtime_health()
    failure = state.get(LAST_SCAN_FAILURE_KEY) or {}
    failure_at = _aware_utc(failure.get("attempted_at")) if isinstance(failure, dict) else None
    failure_is_newer = bool(failure_at and (completed_at is None or failure_at > completed_at))
    stale = bool(auto_scan and scan_age is not None and scan_age > STALE_AUTO_SCAN_SECONDS and not scan_running)

    if native.get("state") == "DEGRADED" or failure_is_newer or stale:
        state_label = "DEGRADED"
    elif completed is None:
        state_label = "STARTING"
    else:
        state_label = "READY"

    reason = ""
    if native.get("state") == "DEGRADED":
        reason = "Webull native radar degraded"
    elif failure_is_newer:
        reason = str(failure.get("message") or "Latest scan attempt failed")
    elif stale:
        reason = f"No completed auto-scan for {int(scan_age or 0)}s"

    return {
        "state": state_label,
        "reason": reason,
        "completed_at": completed_at,
        "scan_age_seconds": scan_age,
        "auto_scan": auto_scan,
        "scan_running": scan_running,
        "scan_requested": scan_requested,
        "webull_native_state": str(native.get("state") or "UNKNOWN"),
        "webull_timeout_count": int(native.get("timeout_count") or 0),
        "suppressed_reruns": int(state.get(SUPPRESSED_RERUNS_KEY, 0) or 0),
        "last_suppressed_rerun_reason": str(state.get("_walter_last_suppressed_rerun_reason") or ""),
    }


def _banner_html(snapshot: dict[str, Any]) -> str:
    state = snapshot["state"]
    reason = snapshot.get("reason") or ""
    age = snapshot.get("scan_age_seconds")
    auto = snapshot.get("auto_scan")
    native = snapshot.get("webull_native_state")
    suppressed = snapshot.get("suppressed_reruns") or 0
    age_text = "no completed scan" if age is None else f"last completed scan {int(age)}s ago"
    mode_text = "auto-scan ON" if auto else "auto-scan OFF"
    tone = "#22c55e" if state == "READY" else "#f59e0b" if state == "STARTING" else "#ef4444"
    reason_html = f" · {reason}" if reason else ""
    return f"""
<!doctype html>
<html><head><style>
body{{margin:0;background:transparent;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#dbe7f3}}
#shell{{border:1px solid #334155;border-left:5px solid {tone};background:#0b1119;border-radius:10px;padding:8px 12px;font-size:13px;line-height:1.35}}
#state{{font-weight:900;color:{tone};letter-spacing:.08em;margin-right:8px}}
#age.stale{{color:#ef4444;font-weight:800}}
.meta{{color:#a8b6c7}}
</style></head>
<body><div id="shell"><span id="state">RUNTIME {state}</span>
<span id="age" data-age="{0 if age is None else int(age)}" data-auto="{1 if auto else 0}">{age_text}</span>
<span class="meta"> · {mode_text} · Webull radar {native} · suppressed reruns {suppressed}{reason_html}</span></div>
<script>
(function(){{
  const ageEl=document.getElementById('age');
  let age=parseInt(ageEl.dataset.age||'0',10);
  const auto=ageEl.dataset.auto==='1';
  const stateEl=document.getElementById('state');
  function tick(){{
    if (auto) {{
      age += 1;
      ageEl.textContent='last completed scan '+age+'s ago';
      if (age>{STALE_AUTO_SCAN_SECONDS}){{
        ageEl.classList.add('stale');
        stateEl.textContent='RUNTIME STALE';
        stateEl.style.color='#ef4444';
        document.getElementById('shell').style.borderLeftColor='#ef4444';
      }}
    }}
    try {{
      const p=window.parent;
      if (p && p.document && /CONNECTING/i.test(p.document.body.innerText||'')) {{
        stateEl.textContent='RUNTIME CONNECTING';
        stateEl.style.color='#ef4444';
        document.getElementById('shell').style.borderLeftColor='#ef4444';
      }}
    }} catch(e) {{}}
  }}
  setInterval(tick,1000);
}})();
</script></body></html>
"""


def render_runtime_truth_banner() -> None:
    """Render a browser-resident health strip that can age while Streamlit stalls."""
    try:
        import streamlit as st
        import streamlit.components.v1 as components
        snapshot = runtime_truth_snapshot(st.session_state)
        components.html(_banner_html(snapshot), height=46, scrolling=False)
    except Exception:
        return


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui
    current = ui.render_walter_mission_control
    if not getattr(current, "_gs355_runtime_truth_banner", False):
        def render_with_runtime_truth(records: list[dict]) -> None:
            render_runtime_truth_banner()
            return current(records)

        _inherit(render_with_runtime_truth, current)
        render_with_runtime_truth._gs355_runtime_truth_banner = True
        render_with_runtime_truth._gs355_original = current
        ui.render_walter_mission_control = render_with_runtime_truth

    # GS356 is intentionally installed from the final existing runtime patch so
    # it remains last in the UI wrapper chain without adding another fragile
    # import-order entry to mide.__init__ during hot deployments.
    from .gs356_client_session_truth import install as _install_gs356_client_session_truth

    _install_gs356_client_session_truth()

    # GS363 is operator presentation/alert only and intentionally installs after
    # the session-truth wrappers so sorting and tiered chimes are the final UI
    # layer without changing any scanner or qualification contract.
    from .gs363_operator_attention_hierarchy import install as _install_gs363_operator_attention_hierarchy

    _install_gs363_operator_attention_hierarchy()
