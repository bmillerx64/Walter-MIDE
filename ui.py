from __future__ import annotations
import base64
import html
from pathlib import Path
import streamlit as st
import pandas as pd


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
    </style>
    """, unsafe_allow_html=True)


def play_alert(sound_path: str, phrase: str):
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
            u.rate = 0.95; u.pitch = 0.9; u.volume = 1.0;
            window.speechSynthesis.speak(u);
          }}
        </script>
        """, height=0
    )


def metric_strip(records):
    statuses = ["EXCEPTIONAL", "ALERT", "WATCH NOW", "MONITOR", "PASS"]
    counts = {k: sum(r["status"] == k for r in records) for k in statuses}
    cols = st.columns(5)
    cols[0].metric("Candidates", len(records))
    cols[1].metric("Exceptional", counts["EXCEPTIONAL"])
    cols[2].metric("Alert / watch", counts["ALERT"] + counts["WATCH NOW"])
    cols[3].metric("Monitor", counts["MONITOR"])
    rising = sum(r.get("velocity", 0) >= 8 for r in records)
    cols[4].metric("Strengthening", rising)


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


def opportunity_card(r):
    klass = {
        "EXCEPTIONAL": "mide-exceptional",
        "ALERT": "mide-alert",
        "WATCH NOW": "mide-watch",
        "MONITOR": "mide-monitor",
    }.get(r["status"], "")
    reasons = " · ".join(r.get("reasons", [])[:6]) or "No qualifying evidence"
    velocity = r.get("velocity", 0)
    arrow = "↑↑" if velocity >= 12 else "↑" if velocity > 2 else "↓" if velocity < -2 else "→"
    tier = r.get("participation_tier", "")
    dominance = r.get("market_dominance_score", 0)
    attention = r.get("attention_score", r["opportunity_score"])
    sections = _why_sections(r)
    evaluated = str(r.get("timestamp", ""))
    last_bar = str(r.get("last_bar_timestamp", ""))
    bar_age = float(r.get("bar_age_seconds", 0) or 0)
    freshness = f"Latest bar {bar_age:.0f}s old" if bar_age else "Latest-bar age unavailable"
    score_boxes = "".join([
        f"<div class='score-box'><div class='score-name'>Priority</div><div class='score-value'>{attention:.1f}</div></div>",
        f"<div class='score-box'><div class='score-name'>Dominance</div><div class='score-value'>{dominance:.1f}</div></div>",
        f"<div class='score-box'><div class='score-name'>Participation</div><div class='score-value'>{r['participation_score']:.1f}</div></div>",
        f"<div class='score-box'><div class='score-name'>Opportunity</div><div class='score-value'>{r['opportunity_score']:.1f}</div></div>",
        f"<div class='score-box'><div class='score-name'>Change</div><div class='score-value'>{arrow} {velocity:+.1f}</div></div>",
    ])
    boxes = "".join(
        f"<div class='why-box'><div class='why-label'>{html.escape(label)}</div>"
        f"<div class='why-text'>{html.escape(text)}</div></div>"
        for label, text in sections.items()
    )
    st.markdown(f"""
    <div class="mide-card {klass}">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <div><span style="font-size:1.55rem;font-weight:800">{html.escape(str(r['symbol']))}</span>
        <span class="small"> ${r['price']:.4f} · {r['pct_change']:+.1f}%</span>
        <span class="tier"> · {html.escape(str(tier))}</span></div>
        <div style="font-size:1.15rem;font-weight:800">{html.escape(str(r['status']))}</div>
      </div>
      <div class="why">{html.escape(reasons)}</div>
      <div class="score-grid">{score_boxes}</div>
      <div class="small"><b>Evidence:</b> Feed volume {r['volume']/1_000_000:.2f}M · Dollar volume ${r['dollar_volume']/1_000_000:.2f}M · RVOL {r.get('rvol_proxy',0):.1f}×</div>
      <div class="freshness">{html.escape(freshness)} · evaluated {html.escape(evaluated[-14:-6] if evaluated else 'now')} UTC</div>
      <div class="why-grid">{boxes}</div>
    </div>
    """, unsafe_allow_html=True)
