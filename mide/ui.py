from __future__ import annotations
import base64
import html
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from mide.scanner_v2 import state_elapsed_seconds
from mide.trader_priority import (
    sortable_text as _sortable_text,
    trader_priority_label,
    trader_priority_sort_key,
)
from mide.time_service import format_eastern_time


def inject_css():
    st.markdown(
        """
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
    .why-summary {margin:10px 0 8px;padding:9px 11px;background:#0c1713;border:1px solid #1f5f46;border-radius:9px}
    .why-summary-title {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#86efac;font-weight:900;margin-bottom:5px}
    .why-summary ul {list-style:none;margin:0;padding:0;display:grid;gap:3px}
    .why-summary li {font-size:.96rem;font-weight:800;color:#eefbf3;line-height:1.35}
    .tier {font-size:.78rem;letter-spacing:.06em;font-weight:800;color:#d9e3ef}
    .market-phase {display:inline-block;margin-left:8px;background:#172033;border:1px solid #314157;border-radius:999px;padding:2px 8px;font-size:.78rem;font-weight:900;color:#eef4fb}
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
    .trend-ladder {display:flex;gap:5px;flex-wrap:wrap;margin-top:7px;font-size:.78rem}
    .trend-step {background:#0c121a;border:1px solid #202c3c;border-radius:999px;padding:2px 7px;font-weight:900}
    .trend-ok {color:#86efac;border-color:#1f7a50}
    .trend-bad {color:#fca5a5;border-color:#7f1d1d}
    .trend-pending {color:#fcd34d;border-color:#854d0e}
    .trend-condition {color:#aeb9c7;font-weight:800;margin-right:3px}
    </style>
    """,
        unsafe_allow_html=True,
    )


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
                  return;
                }}
              }}
              u.rate = 0.95; u.pitch = 0.9; u.volume = 1.0;
              window.speechSynthesis.speak(u);
            }};
            if (window.speechSynthesis.getVoices().length) applyVoice();
            else window.speechSynthesis.onvoiceschanged = applyVoice;
          }}
        </script>
        """,
        height=48 if voice_name else 0,
    )


def scanner_v2_dashboard_counts(records):
    """Return Scanner V2 dashboard counts used by visible metrics and alerts."""
    statuses = [
        "EXCEPTIONAL",
        "ALERT",
        "WATCH NOW",
        "MONITOR",
        "PASS",
        "New",
        "Watching",
        "Emerging",
        "Strengthening",
        "Entry Ready",
        "Weakening",
        "Removed",
    ]
    counts = {
        k: sum((r.get("candidate_status") or r.get("status")) == k for r in records)
        for k in statuses
    }
    return {
        "candidates": len(records),
        "entry_ready": counts["Entry Ready"] + counts["EXCEPTIONAL"],
        "watch_list": counts["Watching"]
        + counts["Emerging"]
        + counts["Strengthening"]
        + counts["ALERT"]
        + counts["WATCH NOW"],
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
        rows.append(
            {
                "Symbol": r["symbol"],
                "Price": r["price"],
                "% Chg": r["pct_change"],
                "Feed Vol": int(r["volume"]),
                "$ Vol": r["dollar_volume"],
                "Attention": r.get(
                    "historical_strength",
                    r.get("attention_score", r["opportunity_score"]),
                ),
                "Dominance": r.get("market_dominance_score", 0),
                "Participation": r["participation_score"],
                "Tier": r.get("participation_tier", ""),
                "Phase": r.get("market_phase", "Emerging"),
                "Opp.": r.get(
                    "current_momentum",
                    r.get("scanner_v2_score", r["opportunity_score"]),
                ),
                "Conv.": r["conviction_score"],
                "Priority": trader_priority_label(r),
                "Status": r["status"],
                "VWAP": r["vwap_relation"],
                "ST": "Bull" if r["supertrend_bullish"] else "Bear",
                "RVOL": r["rvol_proxy"],
                "Vol accel": r["volume_acceleration"],
                "Spread %": r["spread_pct"],
            }
        )
    return pd.DataFrame(rows)


def _why_sections(r):
    participation = []
    if r.get("volume", 0) >= 20_000_000:
        participation.append(f"{r['volume']/1_000_000:.1f}M shares")
    elif r.get("volume", 0) >= 1_000_000:
        participation.append(f"{r['volume']/1_000_000:.1f}M shares")
    participation.append(f"RVOL {r.get('rvol_proxy', 0):.1f}×")
    if r.get("volume_pace_ratio"):
        participation.append(f"VPI {r.get('volume_pace_ratio', 0):.1f}× pace")
    if r.get("acceleration_ratio"):
        participation.append(f"5m acceleration {r.get('acceleration_ratio', 0):.1f}×")
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
    structure.append(
        "SuperTrend bullish"
        if r.get("supertrend_bullish")
        else "SuperTrend not bullish"
    )
    structure.append(
        "above 65 EMA" if r.get("ema65_relation") == "above" else "below 65 EMA"
    )
    if r.get("higher_lows"):
        structure.append("higher lows")
    trend = r.get("trend_confirmation_sequence") or {}
    if trend:
        structure.append(
            f"ST sequence {trend.get('progression_count', 0)}/4 "
            f"{trend.get('condition', '').lower()}"
        )
    else:
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
        if (
            record.get("supertrend_flip")
            or "supertrend flip" in joined
            or "fresh supertrend flip" in joined
        ):
            return fallback
    elif signal == "supertrend":
        if (
            record.get("supertrend_bullish")
            or "supertrend supportive" in joined
            or "supertrend bullish" in joined
        ):
            return fallback
    elif signal == "above_vwap":
        if (
            record.get("vwap_relation") == "above"
            or "above vwap" in joined
            or "vwap reclaim" in joined
        ):
            return fallback
    elif signal == "near_vwap":
        if (
            record.get("vwap_relation") in {"above", "testing"}
            or "near/above vwap" in joined
            or "testing vwap" in joined
        ):
            return "Near VWAP" if record.get("vwap_relation") == "testing" else fallback
    elif signal == "rvol":
        if rvol > 0 or "rvol" in joined:
            direction = (
                " and increasing"
                if "rising rvol" in joined or "rvol improved" in joined
                else ""
            )
            return (
                f"RVOL {rvol:.1f}×{direction}"
                if rvol > 0
                else "Relative volume increasing"
            )
    elif signal == "volume_acceleration":
        if (
            acceleration > 1
            or "accelerating volume" in joined
            or "volume accelerating" in joined
        ):
            return (
                f"Volume accelerating {acceleration:.1f}×"
                if acceleration > 0
                else "Volume accelerating"
            )
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
        if (
            record.get("ema65_relation") == "above"
            or "above 65 ema" in joined
            or "above ema65" in joined
        ):
            return fallback
    return None


def summary_reasons(record):
    """Return the three state-prioritized reasons to headline a stock card."""
    state = record.get("candidate_status") or record.get("status")
    summary_state = _SUMMARY_ALIASES.get(state, state)
    priorities = _SUMMARY_PRIORITIES.get(
        summary_state, _SUMMARY_PRIORITIES["Watch List"]
    )
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
    return _sortable_text(record.get("state_entered_at") or record.get("timestamp"))


def automatic_watching_sort_key(record):
    """Return Walter's automatic live-trading priority for watch-list symbols."""
    return trader_priority_sort_key(record)


SCANNER_V2_DISPLAY_ORDER = (
    "Entry Ready",
    "Strengthening",
    "Watch List",
    "Weak / Removed",
    "Candidates",
)


def state_sections(records):
    """Group Scanner V2 candidates by trading state for dashboard display."""
    sections = {
        "Entry Ready": [],
        "Strengthening": [],
        "Watching": [],
        "Emerging": [],
        "Weakening": [],
        "Removed": [],
    }
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
    for state in sections:
        sections[state].sort(key=trader_priority_sort_key, reverse=True)
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
        pieces.append(
            f"<span class='transition-node'>{html.escape(_state_display_name(str(item.get('state', ''))))}</span>"
        )
        if index + 1 < len(history):
            next_item = history[index + 1]
            next_entered = _parse_transition_time(next_item.get("entered_at"))
            if next_entered is None:
                continue
            seconds = state_elapsed_seconds(
                {"state_entered_at": item.get("entered_at")}, next_entered
            )
            pieces.append(
                f"<span class='transition-arrow'>↓ {html.escape(_format_transition_duration(seconds))}</span>"
            )
    return f"<div class='transition-history'>{''.join(pieces)}</div>"



def trend_ladder_markup(record: dict) -> str:
    """Render a compact 30s→1m→3m→5m SuperTrend confirmation ladder."""
    ladder = record.get("trend_ladder") or (
        (record.get("trend_confirmation_sequence") or {}).get("ladder")
    )
    if not ladder:
        return ""
    condition = html.escape(
        str(
            record.get("trend_condition")
            or (record.get("trend_confirmation_sequence") or {}).get("condition")
            or ""
        )
    )
    pieces = []
    for step in ladder:
        label = html.escape(str(step.get("timeframe", "")))
        state = step.get("state")
        if state == "confirmed":
            glyph, klass = "✔", "trend-ok"
        elif state == "pending":
            glyph, klass = "…", "trend-pending"
        else:
            glyph, klass = "✖", "trend-bad"
        pieces.append(f"<span class='trend-step {klass}'>{label} {glyph}</span>")
    return (
        f"<div class='trend-ladder'><span class='trend-condition'>{condition}</span>"
        f"{''.join(pieces)}</div>"
    )

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
    summary_items = "".join(
        f"<li>✓ {html.escape(reason)}</li>" for reason in headline_reasons
    )
    ladder_markup = trend_ladder_markup(r)
    summary_markup = (
        f"<div class='why-summary'><div class='why-summary-title'>Top reasons now</div><ul>{summary_items}</ul>{ladder_markup}</div>"
        if summary_items
        else f"<div class='why-summary'><div class='why-summary-title'>Top reasons now</div>No qualifying evidence{ladder_markup}</div>"
    )
    promo_badge = (
        "<div class='promo-badge'>Promoted this scan</div>"
        if promoted_this_scan(r)
        else ""
    )
    velocity = r.get("velocity", 0)
    arrow = (
        "↑↑"
        if velocity >= 12
        else "↑" if velocity > 2 else "↓" if velocity < -2 else "→"
    )
    tier = r.get("participation_tier", "")
    market_phase = r.get("market_phase", "Emerging")
    dominance = r.get("market_dominance_score", 0)
    historical_strength = r.get(
        "historical_strength", r.get("attention_score", r["opportunity_score"])
    )
    current_momentum = r.get(
        "current_momentum", r.get("scanner_v2_score", r["opportunity_score"])
    )
    trend_health = r.get("trend_health", "Future")
    score_boxes = "".join(
        [
            f"<div class='score-box'><div class='score-name'>Historical Strength</div><div class='score-value'>{historical_strength:.1f}</div></div>",
            f"<div class='score-box'><div class='score-name'>Current Momentum</div><div class='score-value'>{current_momentum:.1f}</div></div>",
            f"<div class='score-box'><div class='score-name'>Current Phase</div><div class='score-value'>{html.escape(str(market_phase))}</div></div>",
            f"<div class='score-box'><div class='score-name'>Trend Health</div><div class='score-value'>{html.escape(str(trend_health))}</div></div>",
            f"<div class='score-box'><div class='score-name'>Change</div><div class='score-value'>{arrow} {velocity:+.1f}</div></div>",
        ]
    )
    sections = _why_sections(r)
    evaluated = format_eastern_time(r.get("timestamp"), fallback="now")
    state_elapsed = (
        format_state_elapsed(r)
        if r.get("candidate_status") in {"Emerging", "Strengthening", "Entry Ready"}
        else ""
    )
    state_elapsed_markup = (
        f'<span class="small"> · {html.escape(state_elapsed)}</span>'
        if state_elapsed
        else ""
    )
    last_bar = str(r.get("last_bar_timestamp", ""))
    bar_age = float(r.get("bar_age_seconds", 0) or 0)
    freshness = (
        f"Latest bar {bar_age:.0f}s old" if bar_age else "Latest-bar age unavailable"
    )
    boxes = "".join(
        f"<div class='why-box'><div class='why-label'>{html.escape(label)}</div>"
        f"<div class='why-text'>{html.escape(text)}</div></div>"
        for label, text in sections.items()
    )
    st.markdown(
        f"""
    <div class="mide-card {klass}">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <div><span style="font-size:1.55rem;font-weight:800">{html.escape(str(r['symbol']))}</span>{state_elapsed_markup}
        <span class="small"> ${r['price']:.4f} · {r['pct_change']:+.1f}%</span>
        <span class="tier"> · {html.escape(str(tier))}</span><span class="market-phase">Phase: {html.escape(str(market_phase))}</span></div>
        <div style="font-size:1.15rem;font-weight:800">{html.escape(str(r['status']))}</div>
      </div>
      {promo_badge}
      {summary_markup}
      <div class="why">{html.escape(reasons)}</div>
      <div class="score-grid">{score_boxes}</div>
      {transition_history_markup(r)}
      <div class="small"><b>Evidence:</b> Feed volume {r['volume']/1_000_000:.2f}M · Dollar volume ${r['dollar_volume']/1_000_000:.2f}M · RVOL {r.get('rvol_proxy',0):.1f}×</div>
      <div class="freshness">{html.escape(freshness)} · evaluated {html.escape(evaluated)}</div>
      <div class="why-grid">{boxes}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )
