from __future__ import annotations
import base64
import html
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from mide.scanner_v2 import state_elapsed_seconds
from mide.time_service import format_eastern_time


def inject_css():
    st.markdown("""
    <style>
    .block-container {padding-top: 1.1rem; max-width: 1450px;}
    .mide-card {background:#111821;border:1px solid #253143;border-radius:12px;
                padding:14px 16px;margin-bottom:10px;}
    .mide-exceptional {border-left:7px solid #ff2d55; box-shadow:0 0 0 1px rgba(255,45,85,.18);}
    .mide-alert {border-left:5px solid #ff7a45;}
    .mide-watch {border-left:5px solid #f5c542;}
    .mide-monitor {border-left:5px solid #5da9ff;}
    .mide-promoted {border:1px solid #34d399; box-shadow:0 0 18px rgba(52,211,153,.32);}
    .promo-badge {display:inline-block;background:#064e3b;color:#a7f3d0;border:1px solid #34d399;border-radius:999px;padding:3px 9px;margin:6px 0;font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;}
    .small {font-size:.84rem;color:#aeb9c7}
    .why {font-size:.96rem;font-weight:600;line-height:1.5;margin-top:6px}
    .tier {font-size:.78rem;letter-spacing:.06em;font-weight:800;color:#d9e3ef}
    .why-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:10px}
    .why-box {background:#0c121a;border:1px solid #202c3c;border-radius:8px;padding:9px 10px}
    .why-label {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#8190a2;font-weight:800}
    .why-text {font-size:.88rem;color:#d9e3ef;margin-top:5px;line-height:1.45}
    .score-grid {display:grid;grid-template-columns:repeat(5,minmax(105px,1fr));gap:7px;margin:10px 0}
    .score-box {background:#0c121a;border:1px solid #202c3c;border-radius:8px;padding:8px}
    .score-name {font-size:.67rem;text-transform:uppercase;letter-spacing:.07em;color:#8190a2;font-weight:800}
    .score-value {font-size:1.02rem;font-weight:800;color:#eef4fb;margin-top:2px}
    .freshness {font-size:.76rem;color:#8fa0b3;margin-top:7px}
    .transition-history {display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-top:7px;font-size:.78rem;color:#d9e3ef}
    .transition-node {background:#0c121a;border:1px solid #202c3c;border-radius:999px;padding:2px 7px;font-weight:700}
    .transition-arrow {color:#8fa0b3}
    </style>
    """, unsafe_allow_html=True)


def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
    """Play Walter alert audio and speak with the requested Web Speech voice identifier."""
    path = Path(sound_path)
    if not path.exists():
        return
    encoded = base64.b64encode(path.read_bytes()).decode()
    st.components.v1.html(
        f"""
        <audio autoplay><source src="data:audio/wav;base64,{encoded}" type="audio/wav"></audio>
        <script>
          if ('speechSynthesis' in window) {{
            const u = new SpeechSynthesisUtterance({phrase!r});
            const preferred = {voice_name!r};
            const applyVoice = () => {{
              if (preferred) {{
                const voices = window.speechSynthesis.getVoices();
                const voice = voices.find(v => v.voiceURI === preferred || v.name === preferred || v.name.includes(preferred));
                if (voice) {{
                  u.voice = voice;
                }} else {{
                  const warning = `Walter could not load the selected voice: ${{preferred}}.`;
                  console.error(warning);
                  document.body.insertAdjacentHTML(
                    'beforeend',
                    `<div style="padding:8px 10px;border:1px solid #f59e0b;border-radius:6px;background:#451a03;color:#fffbeb;font-family:sans-serif;font-size:13px">${{warning}}</div>`
                  );
                }}
              }}
              u.rate = 0.95; u.pitch = 0.9; u.volume = 1.0;
              window.speechSynthesis.speak(u);
            }};
            if (window.speechSynthesis.getVoices().length) applyVoice();
            else window.speechSynthesis.onvoiceschanged = applyVoice;
          }}
        </script>
        """, height=0
    )


def scanner_v2_dashboard_counts(records):
    """Return Scanner V2 dashboard counts used by visible metrics and alerts."""
    statuses = ["EXCEPTIONAL", "ALERT", "WATCH NOW", "MONITOR", "PASS", "New", "Watching", "Emerging", "Strengthening", "Entry Ready", "Weakening", "Removed"]
    counts = {k: sum((r.get("candidate_status") or r.get("status")) == k for r in records) for k in statuses}
    return {
        "candidates": len(records),
        "entry_ready": counts["Entry Ready"] + counts["EXCEPTIONAL"],
        "watch_list": counts["Watching"] + counts["Emerging"] + counts["Strengthening"] + counts["ALERT"] + counts["WATCH NOW"],
        "weak_removed": counts["Weakening"] + counts["Removed"] + counts["PASS"],
        "strengthening": counts["Strengthening"],
    }


def metric_strip(records):
    metrics = scanner_v2_dashboard_counts(records)
    cols = st.columns(5)
    cols[0].metric("Candidates", metrics["candidates"])
    cols[1].metric("Weak/removed", metrics["weak_removed"])
    cols[2].metric("Watch list", metrics["watch_list"])
    cols[3].metric("Strengthening", metrics["strengthening"])
    cols[4].metric("Entry ready", metrics["entry_ready"])


def radar_table(records):
    rows = []
    for r in records:
        rows.append({
            "Symbol": r["symbol"],
            "Price": r["price"],
            "% Chg": r["pct_change"],
            "Feed Vol": int(r["volume"]),
            "$ Vol": r["dollar_volume"],
            "Attention": r.get("attention_score", r["opportunity_score"]),
            "Dominance": r.get("market_dominance_score", 0),
            "Participation": r["participation_score"],
            "Tier": r.get("participation_tier", ""),
            "Opp.": r["opportunity_score"],
            "Conv.": r["conviction_score"],
            "Status": r["status"],
            "VWAP": r["vwap_relation"],
            "ST": "Bull" if r["supertrend_bullish"] else "Bear",
            "RVOL": r["rvol_proxy"],
            "Vol accel": r["volume_acceleration"],
            "Spread %": r["spread_pct"],
        })
    return pd.DataFrame(rows)


def _why_sections(r):
    participation = []
    if r.get("volume", 0) >= 20_000_000:
        participation.append(f"{r['volume']/1_000_000:.1f}M shares")
    elif r.get("volume", 0) >= 1_000_000:
        participation.append(f"{r['volume']/1_000_000:.1f}M shares")
    participation.append(f"RVOL {r.get('rvol_proxy', 0):.1f}×")
    participation.append(f"acceleration {r.get('volume_acceleration', 0):.1f}×")

    structure = []
    vwap_relation = r.get("vwap_relation")
    vwap_value = r.get("vwap_value")
    if vwap_relation == "above":
        structure.append("above VWAP")
    elif vwap_relation == "testing":
        structure.append("testing VWAP")
    else:
        structure.append("below VWAP")
    if vwap_value:
        structure.append(f"VWAP ${vwap_value:.4f}")
    structure.append("SuperTrend bullish" if r.get("supertrend_bullish") else "SuperTrend not bullish")
    structure.append("above 65 EMA" if r.get("ema65_relation") == "above" else "below 65 EMA")
    if r.get("higher_lows"):
        structure.append("higher lows")
    structure.append(f"{r.get('timeframe_confirmations', 0)}/4 timeframe confirmations")

    headline = r.get("headline") or "No confirmed corporate-news catalyst"
    risk = "; ".join(r.get("cautions", [])[:3]) or "No major model caution"
    return {
        "Participation": " · ".join(participation),
        "Structure": " · ".join(structure),
        "Catalyst": headline,
        "Risk / patience": risk,
    }


def promoted_this_scan(r):
    """Return True only for symbols promoted by the current scan."""
    return bool(r.get("advanced_state") or r.get("entered_watchlist"))


def _state_entered_sort_value(record):
    return record.get("state_entered_at") or record.get("timestamp") or ""


def automatic_watching_sort_key(record):
    """Return Walter's automatic live-trading priority for Watching symbols."""
    return (
        _state_entered_sort_value(record),
        float(record.get("scanner_v2_score", record.get("opportunity_score", 0)) or 0),
        float(record.get("dollar_volume", 0) or 0),
    )


SCANNER_V2_DISPLAY_ORDER = ("Entry Ready", "Strengthening", "Watch List", "Weak / Removed", "Candidates")


def state_sections(records):
    """Group Scanner V2 candidates by trading state for dashboard display."""
    sections = {"Entry Ready": [], "Strengthening": [], "Watching": [], "Emerging": [], "Weakening": [], "Removed": []}
    for record in records:
        state = record.get("candidate_status") or record.get("status")
        if state == "Entry Ready":
            sections["Entry Ready"].append(record)
        elif state == "Strengthening":
            sections["Strengthening"].append(record)
        elif state == "Watching":
            sections["Watching"].append(record)
        elif state in {"Emerging", "New"}:
            sections["Emerging"].append(record)
        elif state == "Weakening":
            sections["Weakening"].append(record)
        else:
            sections["Removed"].append(record)
    for state in ("Entry Ready", "Strengthening", "Emerging"):
        sections[state].sort(key=lambda r: r.get("state_entered_at") or "", reverse=True)
    sections["Watching"].sort(key=automatic_watching_sort_key, reverse=True)
    return sections


def scanner_v2_display_sections(records):
    """Return Scanner V2 sections in the trader review order without changing state logic."""
    sections = state_sections(records)
    return [
        ("Entry Ready", sections["Entry Ready"], True),
        ("Strengthening", sections["Strengthening"], True),
        ("Watch List", sections["Watching"], True),
        ("Weak / Removed", sections["Weakening"] + sections["Removed"], False),
        ("Candidates", sections["Emerging"], False),
    ]


def format_state_elapsed(record, now: datetime | None = None) -> str:
    """Format elapsed time in the current Scanner V2 state as M:SS."""
    seconds = state_elapsed_seconds(record, now)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _format_transition_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, remainder = divmod(seconds, 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s" if remainder else f"{minutes}m"
    return f"{remainder}s"


def _state_display_name(state: str) -> str:
    return "Watch List" if state == "Watching" else state


def _parse_transition_time(value: object) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def transition_history_markup(record: dict) -> str:
    """Render a compact current-session state progression for a symbol card."""
    history = record.get("transition_history") or []
    if len(history) < 2:
        return ""
    pieces = []
    for index, item in enumerate(history):
        pieces.append(f"<span class='transition-node'>{html.escape(_state_display_name(str(item.get('state', ''))))}</span>")
        if index + 1 < len(history):
            next_item = history[index + 1]
            next_entered = _parse_transition_time(next_item.get("entered_at"))
            if next_entered is None:
                continue
            seconds = state_elapsed_seconds({"state_entered_at": item.get("entered_at")}, next_entered)
            pieces.append(f"<span class='transition-arrow'>↓ {html.escape(_format_transition_duration(seconds))}</span>")
    return f"<div class='transition-history'>{''.join(pieces)}</div>"


def opportunity_card(r):
    klass = {
        "EXCEPTIONAL": "mide-exceptional",
        "ALERT": "mide-alert",
        "WATCH NOW": "mide-watch",
        "MONITOR": "mide-monitor",
    }.get(r["status"], "")
    if promoted_this_scan(r):
        klass = f"{klass} mide-promoted".strip()
    reasons = " · ".join(r.get("reasons", [])[:6]) or "No qualifying evidence"
    promo_badge = "<div class='promo-badge'>Promoted this scan</div>" if promoted_this_scan(r) else ""
    velocity = r.get("velocity", 0)
    arrow = "↑↑" if velocity >= 12 else "↑" if velocity > 2 else "↓" if velocity < -2 else "→"
    tier = r.get("participation_tier", "")
    dominance = r.get("market_dominance_score", 0)
    attention = r.get("attention_score", r["opportunity_score"])
    sections = _why_sections(r)
    evaluated = format_eastern_time(r.get("timestamp"), fallback="now")
    state_elapsed = format_state_elapsed(r) if r.get("candidate_status") in {"Emerging", "Strengthening", "Entry Ready"} else ""
    state_elapsed_markup = f'<span class="small"> · {html.escape(state_elapsed)}</span>' if state_elapsed else ""
    last_bar = str(r.get("last_bar_timestamp", ""))
    bar_age = float(r.get("bar_age_seconds", 0) or 0)
    freshness = f"Latest bar {bar_age:.0f}s old" if bar_age else "Latest-bar age unavailable"
    boxes = "".join(
        f"<div class='why-box'><div class='why-label'>{html.escape(label)}</div>"
        f"<div class='why-text'>{html.escape(text)}</div></div>"
        for label, text in sections.items()
    )
    st.markdown(f"""
    <div class="mide-card {klass}">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <div><span style="font-size:1.55rem;font-weight:800">{html.escape(str(r['symbol']))}</span>{state_elapsed_markup}
        <span class="small"> ${r['price']:.4f} · {r['pct_change']:+.1f}%</span>
        <span class="tier"> · {html.escape(str(tier))}</span></div>
        <div style="font-size:1.15rem;font-weight:800">{html.escape(str(r['status']))}</div>
      </div>
      {promo_badge}
      <div class="why">{html.escape(reasons)}</div>
      {transition_history_markup(r)}
      <div class="small"><b>Evidence:</b> Feed volume {r['volume']/1_000_000:.2f}M · Dollar volume ${r['dollar_volume']/1_000_000:.2f}M · RVOL {r.get('rvol_proxy',0):.1f}×</div>
      <div class="freshness">{html.escape(freshness)} · evaluated {html.escape(evaluated)}</div>
      <div class="why-grid">{boxes}</div>
    </div>
    """, unsafe_allow_html=True)
