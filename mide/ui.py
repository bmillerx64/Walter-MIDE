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
    .promo-delta {margin:2px 0 9px;padding:8px 11px;background:#071913;border:1px solid #1f5f46;border-radius:9px;color:#d1fae5;font-size:.9rem;font-weight:750;line-height:1.45}
    .promo-delta ul {list-style:none;margin:0;padding:0;display:grid;gap:3px}
    .promo-delta li::before {content:"+ ";color:#34d399;font-weight:900}
    .small {font-size:.84rem;color:#aeb9c7}
    .why {font-size:.96rem;font-weight:600;line-height:1.5;margin-top:6px}
    .why-summary {margin:10px 0 8px;padding:9px 11px;background:#0c1713;border:1px solid #1f5f46;border-radius:9px}
    .why-summary-title {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#86efac;font-weight:900;margin-bottom:5px}
    .why-summary ul {list-style:none;margin:0;padding:0;display:grid;gap:3px}
    .why-summary li {font-size:.96rem;font-weight:800;color:#eefbf3;line-height:1.35}
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


_SUMMARY_PRIORITIES = {
    "Entry Ready": [
        ("supertrend_flip", "30-second SuperTrend flipped"),
        ("above_vwap", "Above VWAP"),
        ("rvol", None),
        ("dollar_volume", "Dollar volume accelerating"),
        ("volume_acceleration", None),
        ("higher_lows", "Higher lows forming"),
        ("news", "News catalyst"),
        ("ema65", "Above 65 EMA"),
    ],
    "Strengthening": [
        ("news", "News catalyst"),
        ("dollar_volume", "Dollar volume accelerating"),
        ("volume_acceleration", None),
        ("higher_lows", "Higher lows forming"),
        ("rvol", None),
        ("flat_base", "Flat base expanding"),
        ("near_vwap", "Near VWAP"),
        ("supertrend", "SuperTrend supportive"),
    ],
    "Watch List": [
        ("rvol", None),
        ("flat_base", "Flat base maintained"),
        ("near_vwap", "Near VWAP"),
        ("news", "News catalyst"),
        ("dollar_volume", "Dollar volume building"),
        ("higher_lows", "Higher lows forming"),
        ("supertrend", "SuperTrend supportive"),
    ],
}

_SUMMARY_ALIASES = {
    "Watching": "Watch List",
    "Emerging": "Watch List",
    "New": "Watch List",
    "WATCH NOW": "Watch List",
    "ALERT": "Watch List",
    "MONITOR": "Watch List",
    "EXCEPTIONAL": "Entry Ready",
}


def _reason_for_signal(record, signal, fallback):
    reasons = [str(reason) for reason in record.get("reasons", []) if reason]
    joined = " ".join(reasons).lower()
    rvol = float(record.get("rvol_proxy", 0) or 0)
    acceleration = float(record.get("volume_acceleration", 0) or 0)

    if signal == "supertrend_flip":
        if record.get("supertrend_flip") or "supertrend flip" in joined or "fresh supertrend flip" in joined:
            return fallback
    elif signal == "supertrend":
        if record.get("supertrend_bullish") or "supertrend supportive" in joined or "supertrend bullish" in joined:
            return fallback
    elif signal == "above_vwap":
        if record.get("vwap_relation") == "above" or "above vwap" in joined or "vwap reclaim" in joined:
            return fallback
    elif signal == "near_vwap":
        if record.get("vwap_relation") in {"above", "testing"} or "near/above vwap" in joined or "testing vwap" in joined:
            return "Near VWAP" if record.get("vwap_relation") == "testing" else fallback
    elif signal == "rvol":
        if rvol > 0 or "rvol" in joined:
            direction = " and increasing" if "rising rvol" in joined or "rvol improved" in joined else ""
            return f"RVOL {rvol:.1f}×{direction}" if rvol > 0 else "Relative volume increasing"
    elif signal == "volume_acceleration":
        if acceleration > 1 or "accelerating volume" in joined or "volume accelerating" in joined:
            return f"Volume accelerating {acceleration:.1f}×" if acceleration > 0 else "Volume accelerating"
    elif signal == "dollar_volume":
        if record.get("dollar_volume", 0) > 0 or "dollar" in joined:
            return fallback
    elif signal == "higher_lows":
        if record.get("higher_lows") or "higher lows" in joined:
            return fallback
    elif signal == "news":
        headline = record.get("headline")
        if headline or "news" in joined or "catalyst" in joined:
            return fallback
    elif signal == "flat_base":
        if "flat base" in joined:
            return fallback
    elif signal == "ema65":
        if record.get("ema65_relation") == "above" or "above 65 ema" in joined or "above ema65" in joined:
            return fallback
    return None


def summary_reasons(record):
    """Return the three state-prioritized reasons to headline a stock card."""
    state = record.get("candidate_status") or record.get("status")
    summary_state = _SUMMARY_ALIASES.get(state, state)
    priorities = _SUMMARY_PRIORITIES.get(summary_state, _SUMMARY_PRIORITIES["Watch List"])
    selected = []
    seen = set()
    for signal, fallback in priorities:
        reason = _reason_for_signal(record, signal, fallback)
        if reason and reason.lower() not in seen:
            selected.append(reason)
            seen.add(reason.lower())
        if len(selected) == 3:
            return selected
    for reason in record.get("reasons", []):
        clean = str(reason)
        if clean and clean.lower() not in seen:
            selected.append(clean)
            seen.add(clean.lower())
        if len(selected) == 3:
            break
    return selected


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
    headline_reasons = summary_reasons(r)
    summary_items = "".join(f"<li>✓ {html.escape(reason)}</li>" for reason in headline_reasons)
    summary_markup = (
        f"<div class='why-summary'><div class='why-summary-title'>Top reasons now</div><ul>{summary_items}</ul></div>"
        if summary_items else "<div class='why-summary'><div class='why-summary-title'>Top reasons now</div>No qualifying evidence</div>"
    )
    promo_badge = "<div class='promo-badge'>Promoted this scan</div>" if promoted_this_scan(r) else ""
    delta_items = r.get("promotion_delta") or []
    promo_delta = (
        "<div class='promo-delta'><ul>"
        + "".join(f"<li>{html.escape(str(item))}</li>" for item in delta_items)
        + "</ul></div>"
        if promoted_this_scan(r) and delta_items else ""
    )
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
      {promo_delta}
      {summary_markup}
      <div class="why">{html.escape(reasons)}</div>
      <div class="small"><b>Evidence:</b> Feed volume {r['volume']/1_000_000:.2f}M · Dollar volume ${r['dollar_volume']/1_000_000:.2f}M · RVOL {r.get('rvol_proxy',0):.1f}×</div>
      <div class="freshness">{html.escape(freshness)} · evaluated {html.escape(evaluated)}</div>
      <div class="why-grid">{boxes}</div>
    </div>
    """, unsafe_allow_html=True)
