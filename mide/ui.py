from __future__ import annotations
import base64
import html
from mide.version import BUILD
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from mide.escalation import escalation_snapshot, trade_recommendation
from mide.scanner_v2 import state_elapsed_seconds
from mide.trader_priority import (
    sortable_text as _sortable_text,
    trader_priority_label,
    trader_priority_sort_key,
)
from mide.time_service import format_eastern_time
from mide.early_setup import top_timing_setups


DASHBOARD_CSS = """
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
    .decision-row {display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
    .decision-pill {background:#172033;border:1px solid #314157;border-radius:8px;padding:6px 9px}
    .decision-pill b {display:block;font-size:.67rem;letter-spacing:.08em;text-transform:uppercase;color:#8fa0b3}
    .tradeability {font-size:1.05rem;font-weight:900}
    .trade-buyable {color:#4ade80}.trade-wait {color:#facc15}.trade-dont-chase {color:#f87171}
    .coach-box {background:#101827;border:1px solid #334155;border-radius:9px;padding:10px 12px;margin:8px 0}
    .coach-title {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#93c5fd;font-weight:900;margin-bottom:5px}
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
    .trigger-diagnostic {margin:9px 0;padding:9px 11px;background:#101827;border:1px solid #334155;border-radius:9px}
    .trigger-yes {border-color:#22c55e;background:#071b12}
    .trigger-no {border-color:#ef4444;background:#210d12}
    .trigger-title {font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900;color:#e5e7eb;margin-bottom:5px}
    .trigger-diagnostic ul {list-style:none;margin:0;padding:0;display:grid;gap:3px}
    .trigger-diagnostic li {font-size:.92rem;font-weight:800;color:#eef4fb;line-height:1.35}
    .conviction-row {display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:10px 0}
    .conviction-score {font-size:2rem;font-weight:950;color:#f8fafc}
    .conviction-rising {color:#4ade80}.conviction-falling {color:#f87171}.conviction-steady {color:#facc15}
    .conviction-history {display:flex;gap:6px;color:#cbd5e1;font-weight:800}
    .watch-list {list-style:none;margin:5px 0 0;padding:0;display:grid;gap:4px}
    .current-grid {display:grid;grid-template-columns:repeat(5,minmax(125px,1fr));gap:8px;margin:8px 0 12px}
    .current-item {background:#0c121a;border:1px solid #202c3c;border-radius:8px;padding:9px 10px}
    .current-value {font-size:1.15rem;font-weight:900;color:#f8fafc;margin-top:2px}
    .threshold-pass {color:#86efac;font-size:.75rem;font-weight:900}.threshold-fail {color:#fca5a5;font-size:.75rem;font-weight:900}
    .action-box {border:1px solid #60a5fa;background:#0c1728;border-radius:9px;padding:10px 12px;margin:8px 0;font-size:1.25rem;font-weight:950}
    .recommendation-box {border:2px solid var(--recommendation-color);background:#0c121a;border-radius:12px;padding:14px 16px;margin:8px 0 12px}
    .recommendation-label {color:var(--recommendation-color);font-size:1.5rem;font-weight:950;letter-spacing:.04em}
    .recommendation-message {color:#f8fafc;font-size:1rem;font-weight:750;margin-top:4px}
    .context-heading {font-size:.70rem;text-transform:uppercase;letter-spacing:.1em;color:#93a4b8;font-weight:950;margin-top:10px}
    .evidence-list {list-style:none;margin:5px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:3px}
    .hot-card {background:linear-gradient(145deg,#17130c,#111821);border:1px solid #76551c;border-top:3px solid #f59e0b;border-radius:12px;padding:14px 16px;min-height:245px;margin-bottom:14px}
    .hot-rank {color:#fbbf24;font-size:.70rem;font-weight:950;letter-spacing:.10em;text-transform:uppercase}
    .hot-symbol {font-size:1.5rem;font-weight:950;color:#fff7dd;margin:2px 0 8px}
    .hot-confidence {margin:2px 0 10px}
    .hot-confidence-title {font-size:.72rem;text-transform:uppercase;letter-spacing:.12em;color:#d7dee8;font-weight:950;margin-bottom:6px}
    .hot-confidence-track {height:18px;width:100%;overflow:hidden;background:#252c35;border:1px solid #3b4654;border-radius:999px;box-shadow:inset 0 2px 5px rgba(0,0,0,.4)}
    .hot-confidence-fill {height:100%;width:var(--confidence);border-radius:999px;transition:width .55s ease;box-shadow:0 0 12px currentColor}
    .hot-confidence-green {color:#4ade80;background:linear-gradient(90deg,#15803d,#4ade80)}
    .hot-confidence-yellow {color:#facc15;background:linear-gradient(90deg,#a16207,#facc15)}
    .hot-confidence-red {color:#f87171;background:linear-gradient(90deg,#b91c1c,#f87171)}
    .hot-confidence-result {display:flex;align-items:baseline;gap:9px;margin-top:5px}
    .hot-confidence-percent {font-size:2rem;line-height:1;font-weight:950;color:#f8fafc;font-variant-numeric:tabular-nums}
    .hot-confidence-label {font-size:.82rem;letter-spacing:.12em;font-weight:950}
    .hot-confidence-label.hot-confidence-green {color:#4ade80;background:none}
    .hot-confidence-label.hot-confidence-yellow {color:#facc15;background:none}
    .hot-confidence-label.hot-confidence-red {color:#f87171;background:none}
    .opportunity-pulse {display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:5px 10px;margin:7px 0;font-size:.78rem;font-weight:950;letter-spacing:.07em}
    .pulse-green {color:#86efac;background:#073b2a;border:1px solid #22c55e;animation:opportunity-pulse-fade 1.15s ease-out 1}
    .pulse-yellow {color:#fde047;background:#3b3008;border:1px solid #ca8a04}
    .pulse-red {color:#fca5a5;background:#450a0a;border:1px solid #ef4444;animation:opportunity-pulse-fade 1.15s ease-out 1}
    .pulse-dot {font-size:.82rem;line-height:1}
    .pulse-delta {font-variant-numeric:tabular-nums;color:#f8fafc}
    @keyframes opportunity-pulse-fade {0%{box-shadow:0 0 0 0 currentColor;filter:brightness(1.45)}55%{box-shadow:0 0 18px 2px currentColor}100%{box-shadow:0 0 0 0 transparent;filter:brightness(1)}}
    @media (prefers-reduced-motion:reduce){.pulse-green,.pulse-red{animation:none}}
    .hot-heading {font-size:.68rem;text-transform:uppercase;letter-spacing:.09em;color:#aeb9c7;font-weight:900;margin-top:8px}
    .hot-reason {color:#dcfce7;font-size:.90rem;font-weight:750;line-height:1.45}
    .hot-need {color:#fecaca;font-size:.90rem;font-weight:750;line-height:1.4}
    .mission-shell {background:linear-gradient(145deg,#101a27,#0b1119);border:1px solid #334155;border-top:4px solid #60a5fa;border-radius:14px;padding:18px 20px;margin:4px 0 16px;box-shadow:0 12px 30px rgba(0,0,0,.22)}
    .feed-shell {background:#0b1119;border:1px solid #29384b;border-radius:12px;padding:12px 16px;margin:-6px 0 16px;max-height:390px;overflow:hidden}
    .feed-title {font-size:.82rem;letter-spacing:.1em;font-weight:950;color:#dbe7f4;margin-bottom:7px}
    .feed-empty {font-size:.84rem;color:#7f8fa3;padding:3px 0}
    .feed-event {display:grid;grid-template-columns:72px 64px 1fr;gap:9px;align-items:center;border-top:1px solid #1e2937;padding:7px 0;font-size:.88rem;animation:feed-arrival .4s ease-out}
    .feed-time {color:#8291a5;font-variant-numeric:tabular-nums}.feed-symbol {font-weight:950;color:#f8fafc}
    .feed-message {font-weight:750}.feed-green {color:#4ade80}.feed-yellow {color:#facc15}.feed-red {color:#f87171}
    @keyframes feed-arrival {from{background:rgba(96,165,250,.16);transform:translateY(-3px)}to{background:transparent;transform:none}}
    @media (prefers-reduced-motion:reduce){.feed-event{animation:none}}
    .mission-title {font-size:1.25rem;font-weight:950;color:#f8fafc;margin-bottom:13px}
    .mission-monitoring {margin:-3px 0 13px;padding:9px 12px;border:1px solid #ca8a04;border-radius:8px;background:#302707;color:#fde68a;font-size:.9rem;font-weight:900}
    .mission-grid {display:grid;grid-template-columns:minmax(280px,1.35fr) minmax(240px,1fr);gap:12px}
    .mission-target {background:#0c121a;border:1px solid #273548;border-left:6px solid var(--mission-color);border-radius:10px;padding:13px 15px}
    .mission-role {font-size:.68rem;letter-spacing:.13em;text-transform:uppercase;color:#aab7c7;font-weight:950}
    .mission-symbol {font-size:2rem;line-height:1.15;color:#fff;font-weight:950;margin:3px 0}
    .mission-band {color:var(--mission-color);font-size:.76rem;font-weight:950;text-transform:uppercase;letter-spacing:.08em}
    .mission-window-status{color:var(--mission-color);font-size:1.05rem;font-weight:950;margin-top:4px;letter-spacing:.04em}
    .trade-readiness{margin:12px 0 13px;padding:10px 11px;background:#091018;border:1px solid #273548;border-radius:9px}
    .trade-readiness-title{font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:#aab7c7;font-weight:950;margin-bottom:7px}
    .trade-readiness-track{display:grid;grid-template-columns:repeat(5,1fr);gap:4px}
    .trade-readiness-step{height:13px;background:#263241;border:1px solid #39485a;border-radius:3px}
    .trade-readiness-step.is-reached{background:var(--readiness-color);border-color:var(--readiness-color);box-shadow:0 0 8px color-mix(in srgb,var(--readiness-color) 55%,transparent)}
    .trade-readiness-labels{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin-top:5px}
    .trade-readiness-label{color:#6f8094;font-size:.56rem;font-weight:900;text-align:center;white-space:nowrap}
    .trade-readiness-label.is-current{color:var(--readiness-color)}
    .trade-readiness-state{color:var(--readiness-color);font-size:1.05rem;font-weight:950;letter-spacing:.08em;margin-top:8px}
    .trade-readiness-sentence{color:#e2e8f0;font-size:.88rem;font-weight:800;margin-top:3px}
    .trade-readiness.is-entry-window .trade-readiness-step.is-reached{animation:readiness-open 1.6s ease-out 1}
    @keyframes readiness-open{0%,100%{filter:brightness(1);box-shadow:0 0 8px rgba(74,222,128,.4)}45%{filter:brightness(1.5);box-shadow:0 0 20px rgba(74,222,128,.9)}}
    .mission-status {font-size:1.05rem;font-weight:850;color:#e2e8f0;margin:8px 0}
    .mission-meta {font-size:.84rem;color:#aeb9c7;margin-top:4px}.mission-meta b{color:#f8fafc}
    .opportunity-meter {margin:10px 0 12px}.opportunity-meter-top{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:6px}
    .opportunity-meter-label{font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;color:#aab7c7;font-weight:950}.opportunity-meter-value{font-size:1.55rem;color:#f8fafc;font-weight:950;font-variant-numeric:tabular-nums}
    .opportunity-meter-value small{font-size:.78rem;margin-left:5px}.meter-delta-up{color:#4ade80}.meter-delta-down{color:#f87171}
    .opportunity-meter-track{height:15px;overflow:hidden;background:#202a36;border:1px solid #3b4a5c;border-radius:999px;box-shadow:inset 0 2px 4px rgba(0,0,0,.35)}
    .opportunity-meter-fill{height:100%;width:var(--opportunity);background:linear-gradient(90deg,#ca8a04,#facc15);border-radius:999px;transition:width .55s ease}
    .mission-section-title{color:#fde047;font-size:.68rem;letter-spacing:.12em;font-weight:950;margin-top:9px}
    .mission-reasons,.mission-path{display:grid;gap:2px;margin-top:4px}
    .mission-reason{color:#dcfce7;font-size:.88rem;font-weight:850;line-height:1.35}
    .mission-check{color:#f8fafc;font-size:.90rem;font-weight:850;line-height:1.4}
    .mission-why-not{margin-top:9px;padding-top:8px;border-top:1px solid #273548;color:#cbd5e1;font-size:.86rem;font-weight:800}.mission-why-not b{display:block;color:#fca5a5;font-size:.68rem;letter-spacing:.12em;margin-bottom:3px}
    .decision-narrative{margin-top:10px;padding:10px 11px;border:1px solid #334155;border-radius:8px;background:#101827;color:#e2e8f0;font-size:.84rem;line-height:1.45}.decision-narrative b{display:block;color:#93c5fd;font-size:.68rem;letter-spacing:.1em;margin-bottom:4px}
    .mission-condition-met{display:inline-block;color:#86efac;font-size:.84rem;font-weight:900;margin-top:8px;animation:condition-flash 1.35s ease-out 1}
    .entry-window-open{margin:10px 0 5px;padding:11px 12px;text-align:center;border:1px solid #4ade80;border-radius:8px;background:#064e3b;color:#dcfce7;font-size:1.15rem;font-weight:950;letter-spacing:.11em}
    .entry-window-pulse{animation:entry-window-pulse 2s ease-out 1}
    @keyframes condition-flash{0%{background:#f8fafc;color:#064e3b;box-shadow:0 0 22px #4ade80}100%{background:transparent;color:#86efac;box-shadow:none}}
    @keyframes entry-window-pulse{0%,100%{box-shadow:0 0 0 rgba(74,222,128,0)}25%,70%{box-shadow:0 0 30px rgba(74,222,128,.75);border-color:#86efac}}
    @media(prefers-reduced-motion:reduce){.mission-condition-met,.entry-window-pulse,.trade-readiness.is-entry-window .trade-readiness-step.is-reached{animation:none}}
    .mission-ignore {margin-top:11px;padding-top:10px;border-top:1px solid #273548;color:#94a3b8;font-size:.82rem}
    .control-header {background:linear-gradient(145deg,#0b1722,#0a1018);border:1px solid #334155;border-top:4px solid #38bdf8;border-radius:14px;padding:15px 18px;margin:2px 0 10px;box-shadow:0 12px 30px rgba(0,0,0,.22)}
    .control-heading {display:flex;align-items:flex-end;justify-content:space-between;gap:14px;flex-wrap:wrap}
    .control-title {font-size:1.55rem;line-height:1.15;font-weight:950;color:#f8fafc}.control-version{font-size:.84rem;color:#7dd3fc;font-weight:900;margin-top:3px}
    .control-engine {font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;font-weight:850}
    .control-strip {display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:7px;margin-top:13px}
    .control-stat {background:#0c121a;border:1px solid #253244;border-radius:8px;padding:8px 9px;min-width:0}
    .control-stat-label {font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:#8291a5;font-weight:900;white-space:nowrap}
    .control-stat-value {font-size:.96rem;color:#f8fafc;font-weight:950;margin-top:3px;white-space:normal;overflow-wrap:anywhere;line-height:1.2;font-variant-numeric:tabular-nums}
    .control-live{color:#4ade80}.control-demo{color:#facc15}
    .scan-trust {display:grid;grid-template-columns:minmax(250px,1.5fr) repeat(3,minmax(100px,.5fr));gap:10px;align-items:center;background:#0b131d;border:1px solid #334155;border-left:6px solid var(--trust-color);border-radius:10px;padding:10px 14px;margin:-3px 0 12px}
    .scan-trust-title {color:var(--trust-color);font-size:.94rem;font-weight:950;letter-spacing:.04em}.scan-trust-reason{color:#cbd5e1;font-size:.78rem;margin-top:2px}
    .scan-trust-stat span{display:block;color:#8291a5;font-size:.6rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.scan-trust-stat b{color:#f8fafc;font-size:1rem;font-variant-numeric:tabular-nums}
    .market-day {display:grid;grid-template-columns:minmax(240px,1.25fr) minmax(330px,2fr);gap:14px;align-items:center;background:#0b131d;border:1px solid #334155;border-left:6px solid var(--market-color);border-radius:11px;padding:11px 15px;margin:-2px 0 12px}
    .market-day-title {font-size:.65rem;letter-spacing:.13em;color:#94a3b8;font-weight:950}
    .market-day-mode {font-size:1.28rem;color:var(--market-color);font-weight:950;margin:2px 0}
    .market-day-guidance {font-size:.9rem;color:#e2e8f0;font-weight:850}
    .market-day-confidence {font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;font-weight:900}.market-day-confidence b{font-size:1.25rem;color:#f8fafc;margin-left:5px}
    .market-day-metrics {display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;margin-top:7px}
    .market-day-metric {border-left:1px solid #334155;padding-left:8px}.market-day-metric span{display:block;font-size:.58rem;line-height:1.15;text-transform:uppercase;letter-spacing:.06em;color:#8291a5;font-weight:850}.market-day-metric b{font-size:.9rem;color:#f8fafc;font-variant-numeric:tabular-nums}
    .escalation-card {background:#0b131d;border:1px solid #334155;border-left:6px solid var(--escalation-color);border-radius:11px;padding:13px 15px;margin:8px 0}
    .escalation-top {display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
    .escalation-symbol {font-size:1.35rem;font-weight:950;color:#f8fafc}.escalation-state {font-weight:950;color:var(--escalation-color)}
    .escalation-trend {font-size:.82rem;color:#cbd5e1;font-weight:800}.escalation-details {display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:9px}
    .escalation-list {list-style:none;padding:0;margin:5px 0 0;display:grid;gap:3px;font-size:.83rem}.delta-up{color:#86efac}.delta-down{color:#fca5a5}
    @media(max-width:760px){.mission-grid{grid-template-columns:1fr}.market-day{grid-template-columns:1fr}}
    @media(max-width:760px){.escalation-details{grid-template-columns:1fr}}
    </style>
    """


def inject_css():
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)


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


def early_setups_markup(records: list[dict]) -> str:
    """Render the five charts Walter is most likely to want opened now."""
    cards = []
    for record in top_timing_setups(records):
        detail = record.get("early_setup") or {}
        structure = record.get("structure") or detail.get("structure") or {}
        if detail.get("timing_state") in {"LATE MOMENTUM", "WAIT FOR RESET"}:
            cards.append(
                f'<div class="mide-card mide-watch">{timing_status_markup(record)}</div>'
            )
            continue
        float_millions = structure.get("float_millions")
        float_text = (
            f"{float(float_millions):.1f}M" if float_millions is not None else "unknown"
        )
        participation = (
            "accelerating" if structure.get("participation_accelerating") else "steady"
        )
        cards.append(
            f'<div class="mide-card mide-watch"><b>{html.escape(str(record.get("symbol") or "").upper())}</b> '
            f'${float(record.get("price") or 0):.2f} &nbsp; {float(record.get("pct_change") or 0):+.1f}%<br>'
            f'<b>⚡ {html.escape(str(structure.get("state") or "BUILDING"))}</b> · Structure Score {float(structure.get("score") or 0):.0f}<br>'
            f'VWAP {html.escape(str(structure.get("vwap_status") or "unknown"))} · '
            f'SuperTrend {float(structure.get("supertrend_distance_pct") or 0):.2f}% away<br>'
            f"Participation {participation} · Float {float_text}<br>"
            f'<span class="small">Probability of breakout <b>{float(structure.get("probability_of_breakout") or 0):.0f}%</b></span></div>'
        )
    body = (
        "".join(cards)
        if cards
        else '<div class="feed-empty">No developing ignition structures right now.</div>'
    )
    return f'<div class="feed-shell"><div class="feed-title">⚡ STRUCTURE ENGINE</div>{body}</div>'


def timing_status_markup(record: dict) -> str:
    """Render the timing verdict without presenting late discovery as early."""
    detail = record.get("early_setup") or {}
    state = str(
        detail.get("timing_state") or record.get("timing_state") or "Discovered"
    )
    symbol = html.escape(str(record.get("symbol") or "").upper())
    if state not in {"LATE MOMENTUM", "WAIT FOR RESET"}:
        return f"<b>{symbol}</b><br>{html.escape(state.title())}"
    move = float(detail.get("percent_move_since_first_detection") or 0)
    return (
        f"<b>{symbol}</b><br>Late Momentum<br>"
        f"Detected {move:+.0f}% after ignition<br>Wait for reset"
    )


def render_early_setups(records: list[dict]) -> None:
    st.markdown(early_setups_markup(records), unsafe_allow_html=True)


def is_actionable_candidate(record: dict) -> bool:
    """Return whether a scanner record belongs in the visible workflow."""
    if "qualified_for_watch" in record:
        return record["qualified_for_watch"] is not False
    # TODO Walter 2.0 Phase 2: remove the legacy ranking fallback once stored
    # Scanner V1/V2 records have been migrated.
    return record.get("qualified_for_ranking", True) is not False


def actionable_candidate_records(records: list[dict]) -> list[dict]:
    """Return records qualified for watch-workflow display."""
    return [record for record in records if is_actionable_candidate(record)]


def rejected_candidate_records(records: list[dict]) -> list[dict]:
    """Return diagnostic-only records rejected before the Watching workflow."""
    return [record for record in records if not is_actionable_candidate(record)]


def _actual_and_required(evidence: list[str], result: str) -> tuple[str, str]:
    """Extract display values from the decision engine's existing audit evidence."""
    actual = next(
        (
            item.split(":", 1)[1].strip()
            for item in evidence
            if item.startswith("Actual:")
        ),
        "",
    )
    required = ""
    for item in evidence:
        if item.startswith("Limit:"):
            required = "<= " + item.split(":", 1)[1].strip()
            break
        if item.startswith("Range:"):
            required = item.split(":", 1)[1].strip()
            break
    agreement = next((item for item in evidence if "categories agree" in item), "")
    if agreement:
        actual = agreement.split(" ", 1)[0]
        required = ">= 3/5 categories agree"
    return actual or result, required or "Pass"


def rejection_diagnostics(
    records: list[dict],
    stage2_rejections: list[dict] | None = None,
    *,
    prefilter_rejections: list[dict] | None = None,
    timestamp="",
) -> list[dict]:
    """Normalize existing Stage 2+ failures into presentation-only audit rows."""
    rows: list[dict] = []
    for rejected in stage2_rejections or []:
        evidence = list(rejected.get("evidence") or [])
        actual, required = _actual_and_required(
            evidence, str(rejected.get("result") or "")
        )
        rows.append(
            {
                "Symbol": str(rejected.get("symbol") or "").upper(),
                "Stage": rejected.get("stage") or "Stage 2",
                "Rule": rejected.get("reason") or "Unknown",
                "Actual Value": actual,
                "Required Threshold": required,
                "Timestamp": timestamp,
            }
        )
    for rejected in prefilter_rejections or []:
        measured = rejected.get("measured_values") or {}
        thresholds = rejected.get("thresholds") or {}
        price = float(measured.get("price") or 0)
        change = float(measured.get("pct_change") or 0)
        volume = float(measured.get("volume") or 0)
        dollar_volume = float(measured.get("dollar_volume") or 0)
        if not thresholds.get("min_price", 0) <= price <= thresholds.get(
            "max_price", float("inf")
        ):
            rule = "Price"
            actual = f"${price:.2f}"
            required = (
                f"${thresholds.get('min_price', 0):.2f}–"
                f"${thresholds.get('max_price', 0):.2f}"
            )
        elif change < thresholds.get("min_pct_change", 0) and volume < thresholds.get(
            "min_day_volume", 0
        ):
            rule = "Percent Change or Day Volume"
            actual = f"{change:+.2f}% / {volume:,.0f} shares"
            required = (
                f">= {thresholds.get('min_pct_change', 0):g}% or >= "
                f"{thresholds.get('min_day_volume', 0):,.0f} shares"
            )
        else:
            rule = "Dollar Volume"
            actual = f"${dollar_volume:,.0f}"
            required = f">= ${thresholds.get('min_dollar_volume', 0):,.0f}"
        rows.append(
            {
                "Symbol": str(rejected.get("symbol") or "").upper(),
                "Stage": "Stage 2 Prefilter",
                "Rule": rule,
                "Actual Value": actual,
                "Required Threshold": required,
                "Timestamp": timestamp,
            }
        )
    for record in records:
        if record.get("final_decision") != "Rejected":
            continue
        failed = next(
            (
                step
                for step in reversed(record.get("decision_funnel") or [])
                if not step.get("passed", True)
            ),
            {},
        )
        evidence = list(failed.get("evidence") or [])
        actual, required = _actual_and_required(
            evidence, str(failed.get("result") or "")
        )
        rows.append(
            {
                "Symbol": str(record.get("symbol") or "").upper(),
                "Stage": record.get("current_stage")
                or f"Stage {failed.get('stage', '')}".strip(),
                "Rule": failed.get("category")
                or record.get("rejection_reason")
                or "Unknown",
                "Actual Value": actual,
                "Required Threshold": required,
                "Timestamp": timestamp,
            }
        )
    return rows


def rejected_candidates_table(records: list[dict]) -> pd.DataFrame:
    """Build the sortable, most-recent-first rejection diagnostics table."""
    columns = [
        "Symbol",
        "Stage",
        "Rule",
        "Actual Value",
        "Required Threshold",
        "Timestamp",
    ]
    return pd.DataFrame(records[:100], columns=columns)


def scanner_v2_dashboard_counts(records):
    """Return Scanner V2 dashboard counts used by visible metrics and alerts."""
    records = actionable_candidate_records(records)
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


def mission_control_header_markup(
    *,
    live: bool,
    market_phase: str,
    market_time: str,
    symbols_sampled: int,
    prefilter_count: int,
    candidate_count: int,
    focus_count: int,
    escalation_count: int,
    auto_scan: str,
    funnel_counts: dict | None = None,
) -> str:
    """Build the compact, presentation-only Mission Control header."""
    status = "🟢 LIVE" if live else "🟡 DEMO"
    status_class = "control-live" if live else "control-demo"
    stats = (
        ("Status", status, status_class, "walter-status"),
        ("Market phase", market_phase, "", "walter-market-phase"),
        ("Market time", market_time, "", "walter-market-time"),
        ("Symbols", str(symbols_sampled), "", "walter-symbols"),
        ("Prefiltered", str(prefilter_count), "", "walter-prefiltered"),
        ("Candidates", str(candidate_count), "", "walter-candidates"),
        ("Focus", str(focus_count), "", "walter-focus"),
        ("Escalating", str(escalation_count), "", "walter-escalating"),
        ("Auto scan", auto_scan, "", "walter-auto-scan"),
    )
    strip = "".join(
        f"<div class='control-stat'><div class='control-stat-label'>{html.escape(label)}</div>"
        f"<div id='{element_id}' class='control-stat-value {css_class}'>{html.escape(value)}</div></div>"
        for label, value, css_class, element_id in stats
    )
    funnel = ""
    if funnel_counts:
        labels = (
            ("universe", "Universe"), ("tradability", "Tradability"),
            ("stage_3_analysis", "Stage 3 Analysis"), ("monitored", "Monitored"),
            ("entry_ready", "Entry Ready"),
        )
        before_float = " → ".join(
            f"{label}: {int(funnel_counts[key])}"
            for key, label in labels[:2] if key in funnel_counts
        )
        after_float = " → ".join(
            f"{label}: {int(funnel_counts[key])}"
            for key, label in labels[2:] if key in funnel_counts
        )
        price_survivors = int(funnel_counts.get("price", 0))
        evaluated = int(funnel_counts.get("free_float_evaluated", price_survivors))
        passed = int(funnel_counts.get("free_float", 0))
        failed = int(funnel_counts.get("free_float_failed", max(0, evaluated - passed)))
        lookup_failures = int(funnel_counts.get("free_float_lookup_failures", 0))
        actual_failures = int(funnel_counts.get("free_float_actual_failures", max(0, failed - lookup_failures)))
        float_summary = (
            f"Price Survivors: {price_survivors} ↓ Free Float: {passed} "
            f"({evaluated} evaluated) · {passed} passed · {failed} failed · "
            f"Lookup failures: {lookup_failures} · Actual failures: {actual_failures}"
        )
        parts = [part for part in (before_float, float_summary, after_float) if part]
        funnel = "<div class='small'><b>Stage Summary</b><br>" + " → ".join(parts) + "</div>"
    return (
        "<div class='control-header'><div class='control-heading'><div>"
        "<div class='control-title'>🛰 Walter • MIDE Radar</div>"
        f"<div class='control-version'>v{html.escape(BUILD.version)} · "
        f"{html.escape(BUILD.git_sha)} · {html.escape(BUILD.built_at)}</div></div>"
        "<div class='control-engine'>Market Intelligence Decision Engine</div></div>"
        f"<div class='control-strip'>{strip}</div>{funnel}</div>"
    )


def data_integrity_markup(report: dict) -> str:
    """Render a compact, presentation-only scan-trust summary."""
    appearances = {
        "AWAITING SCAN": ("⚪", "#94a3b8"),
        "HEALTHY SCAN": ("🟢", "#4ade80"),
        "VALID EMPTY PASS": ("🔵", "#60a5fa"),
        "DEGRADED DATA": ("🟠", "#f59e0b"),
        "PROVIDER / PIPELINE FAILURE": ("🔴", "#f87171"),
    }
    status = str(report.get("status", "DEGRADED DATA"))
    icon, color = appearances.get(status, ("🟠", "#f59e0b"))

    def percentage(value: object) -> str:
        if value is None:
            return "N/A"
        return f"{float(value):.0f}%"

    trust = (
        "NOT YET MEASURED"
        if status == "AWAITING SCAN"
        else percentage(report.get("trust_score"))
    )
    integrity = percentage(report.get("record_integrity_pct"))
    freshness = percentage(report.get("freshness_pct"))
    unique = int(report.get("unique_symbols", 0) or 0)
    records = int(report.get("record_count", 0) or 0)
    reason = html.escape(str(report.get("status_reason", "No diagnostic reason available.")))
    return (
        f"<div class='scan-trust' style='--trust-color:{color}'>"
        "<div><div class='scan-trust-title'>"
        f"{icon} SCAN TRUST — {html.escape(status)} · {trust}</div>"
        f"<div class='scan-trust-reason'>{reason}</div></div>"
        f"<div class='scan-trust-stat'><span>Integrity</span><b>{integrity}</b></div>"
        f"<div class='scan-trust-stat'><span>Freshness</span><b>{freshness}</b></div>"
        f"<div class='scan-trust-stat'><span>Unique / Records</span><b>{unique} / {records}</b></div>"
        "</div>"
    )


def decision_funnel_markup(record: dict) -> str:
    """Render an audit trail without interpreting or changing its decisions."""
    steps = record.get("decision_funnel") or []
    rows = []
    for step in steps:
        mark = "✓" if step.get("passed") else "✕"
        evidence = " · ".join(str(item) for item in step.get("evidence") or [] if item)
        rows.append(
            "<div class='funnel-step'>"
            f"<b>{mark} Stage {int(step.get('stage', 0))} — {html.escape(str(step.get('category', '')))}</b>"
            f"<br>{html.escape(str(step.get('result', '')))}"
            + (f"<br><span class='small'>{html.escape(evidence)}</span>" if evidence else "")
            + "</div>"
        )
    return (
        "<div class='control-card'><b>Decision Funnel</b>"
        + "<div class='small'>Stage 1 ↓ Stage 2 ↓ Stage 3 ↓ Current Stage ↓ Final Decision</div>"
        + "".join(rows)
        + f"<hr><b>Current Stage:</b> {html.escape(str(record.get('current_stage', 'Unknown')))}"
        + f"<br><b>Final Decision:</b> {html.escape(str(record.get('final_decision', 'Pending')))}</div>"
    )


def market_session_quality(records: list[dict], *, snapshot_metrics: dict | None = None) -> dict:
    """Summarize session-wide scanner evidence without changing candidate ranking."""
    records = actionable_candidate_records(records)
    counts = scanner_v2_dashboard_counts(records)
    total = len(records)

    def average(primary: str, fallback: str | None = None) -> float:
        values = []
        for record in records:
            value = record.get(primary)
            if value is None and fallback:
                value = record.get(fallback)
            if value is not None:
                values.append(_bounded_score(value))
        return sum(values) / len(values) if values else 0.0

    participation = average("participation_surge_score", "participation_score")
    expansion = average("expansion_quality")
    news_symbols = sum(
        bool(str(record.get("headline") or "").strip()) for record in records
    )

    if not records and snapshot_metrics and snapshot_metrics.get("symbol_count", 0) > 0:
        # No candidates survived the pipeline; derive a broad market signal from
        # raw snapshot price/volume data so the panel reflects real market activity
        # rather than showing a trivial zero computed from an empty input set.
        n = snapshot_metrics["symbol_count"]
        pct_above = snapshot_metrics.get("symbols_above_pct_threshold", 0)
        vol_above = snapshot_metrics.get("symbols_above_volume_threshold", 0)
        avg_pct = snapshot_metrics.get("avg_pct_change", 0.0)
        avg_dvol = snapshot_metrics.get("avg_dollar_volume", 0.0)
        # Normalise: what fraction of the scanned universe shows any momentum or volume.
        activity_ratio = (pct_above + vol_above) / (2 * n)
        # Mild bonus for average move size (cap at 10% gain = full bonus).
        pct_bonus = min(avg_pct / 10.0, 1.0) * 10
        # Mild bonus for dollar volume ($500K average = full bonus).
        dvol_bonus = min(avg_dvol / 500_000, 1.0) * 10
        confidence = round(max(0, min(100, activity_ratio * 80 + pct_bonus + dvol_bonus)))
        if confidence >= 75:
            mode, guidance, color = (
                "🟢 MOMENTUM DAY",
                "Trade strong setups aggressively.",
                "#4ade80",
            )
        elif confidence >= 55:
            mode, guidance, color = "🟡 SELECTIVE DAY", "Trade only A setups.", "#facc15"
        elif confidence >= 35:
            mode, guidance, color = (
                "🟠 CHOPPY DAY",
                "Be patient. Reduce position size.",
                "#fb923c",
            )
        elif confidence > 0:
            mode, guidance, color = (
                "🔴 DEAD TAPE",
                "Protect capital. Avoid forcing trades.",
                "#f87171",
            )
        else:
            mode, guidance, color = (
                "🔇 QUIET MARKET",
                "No active setups. Stand aside.",
                "#94a3b8",
            )
        return {
            "mode": mode,
            "guidance": guidance,
            "color": color,
            "confidence": confidence,
            "qualified": 0,
            "strengthening": 0,
            "entry_ready": 0,
            "average_participation": 0,
            "average_expansion": 0,
            "news_symbols": 0,
            "snapshot_based": True,
        }

    # All inputs are already-produced scanner evidence. Count caps prevent a large
    # universe alone from overstating the quality of the trading environment.
    confidence = round(
        participation * 0.30
        + expansion * 0.30
        + min(total / 10, 1) * 15
        + min(counts["strengthening"] / 4, 1) * 10
        + min(counts["entry_ready"] / 3, 1) * 10
        + min(news_symbols / 4, 1) * 5
    )
    confidence = max(0, min(100, confidence))
    if confidence >= 75:
        mode, guidance, color = (
            "🟢 MOMENTUM DAY",
            "Trade strong setups aggressively.",
            "#4ade80",
        )
    elif confidence >= 55:
        mode, guidance, color = "🟡 SELECTIVE DAY", "Trade only A setups.", "#facc15"
    elif confidence >= 35:
        mode, guidance, color = (
            "🟠 CHOPPY DAY",
            "Be patient. Reduce position size.",
            "#fb923c",
        )
    else:
        mode, guidance, color = (
            "🔴 DEAD TAPE",
            "Protect capital. Avoid forcing trades.",
            "#f87171",
        )
    return {
        "mode": mode,
        "guidance": guidance,
        "color": color,
        "confidence": confidence,
        "qualified": total,
        "strengthening": counts["strengthening"],
        "entry_ready": counts["entry_ready"],
        "average_participation": round(participation),
        "average_expansion": round(expansion),
        "news_symbols": news_symbols,
    }


def market_session_quality_markup(records: list[dict], *, snapshot_metrics: dict | None = None) -> str:
    """Build the compact Today's Market panel from aggregate session evidence."""
    session = market_session_quality(records, snapshot_metrics=snapshot_metrics)
    if session.get("snapshot_based") and snapshot_metrics:
        # Show raw snapshot signals; pipeline scores are not available.
        n = snapshot_metrics.get("symbol_count", 0)
        metrics = (
            ("Symbols Scanned", n),
            ("Movers ≥ {}%".format(int(snapshot_metrics.get("pct_change_threshold", 3))),
             snapshot_metrics.get("symbols_above_pct_threshold", 0)),
            ("Vol ≥ {}K".format(int(snapshot_metrics.get("volume_threshold", 100_000) // 1000)),
             snapshot_metrics.get("symbols_above_volume_threshold", 0)),
            ("Avg Move", f'{snapshot_metrics.get("avg_pct_change", 0.0):.1f}%'),
            ("Max Move", f'{snapshot_metrics.get("max_pct_change", 0.0):.1f}%'),
            ("Avg $ Vol", f'${snapshot_metrics.get("avg_dollar_volume", 0):,.0f}'),
        )
    else:
        metrics = (
            ("Qualified", session["qualified"]),
            ("Strengthening", session["strengthening"]),
            ("Entry Ready", session["entry_ready"]),
            ("Avg Participation", f'{session["average_participation"]}%'),
            ("Avg Expansion", f'{session["average_expansion"]}%'),
            ("News Symbols", session["news_symbols"]),
        )
    metric_html = "".join(
        f"<div class='market-day-metric'><span>{html.escape(label)}</span><b>{html.escape(str(value))}</b></div>"
        for label, value in metrics
    )
    return (
        f"<div class='market-day' style='--market-color:{session['color']}'><div>"
        "<div class='market-day-title'>TODAY'S MARKET</div>"
        f"<div class='market-day-mode'>{session['mode']}</div>"
        f"<div class='market-day-guidance'>{html.escape(session['guidance'])}</div></div><div>"
        f"<div class='market-day-confidence'>Market Confidence <b>{session['confidence']}%</b></div>"
        f"<div class='market-day-metrics'>{metric_html}</div></div></div>"
    )


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
                "RS Score": r.get("relative_strength_score"),
                "Participation": r["participation_score"],
                "Tier": r.get("participation_tier", ""),
                "Phase": r.get("market_phase", "Emerging"),
                "Opp.": r.get(
                    "current_momentum",
                    r.get("scanner_v2_score", r["opportunity_score"]),
                ),
                "Conv.": r.get("conviction_v2_score", r["conviction_score"]),
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
        participation.append(f"{r['volume'] / 1_000_000:.1f}M shares")
    elif r.get("volume", 0) >= 1_000_000:
        participation.append(f"{r['volume'] / 1_000_000:.1f}M shares")
    participation.append(f"RVOL {r.get('rvol_proxy', 0):.1f}×")
    if r.get("volume_pace_ratio"):
        participation.append(f"VPI {r.get('volume_pace_ratio', 0):.1f}× pace")
    if r.get("acceleration_ratio"):
        participation.append(f"5m acceleration {r.get('acceleration_ratio', 0):.1f}×")
    participation.append(f"acceleration {r.get('volume_acceleration', 0):.1f}×")
    if r.get("participation_surge_score") is not None:
        participation.append(
            f"Participation Surge {r.get('participation_surge_score', 0):.0f}/100"
        )

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
        structure.append(
            f"{r.get('timeframe_confirmations', 0)}/4 timeframe confirmations"
        )

    headline = r.get("headline") or "No confirmed corporate-news catalyst"
    risk = "; ".join(r.get("cautions", [])[:3]) or "No major model caution"
    stability = r.get("trend_stability_diagnostics") or {}
    stability_factors = stability.get("factors") or {}
    stability_text = (
        " · ".join(
            [
                f"VWAP Stability {float(stability_factors.get('vwap_stability', 0) or 0):.0f}",
                f"ST Stability {float(stability_factors.get('st_stability', 0) or 0):.0f}",
                f"Pullback Quality {float(stability_factors.get('pullback_quality', 0) or 0):.0f}",
                f"Continuation Strength {float(stability_factors.get('continuation_strength', 0) or 0):.0f}",
            ]
        )
        if stability_factors
        else "Trend stability unavailable"
    )
    quality = r.get("momentum_quality_diagnostics") or {}
    factors = quality.get("factors") or {}
    quality_text = (
        " · ".join(
            [
                f"VWAP Respect {float(factors.get('vwap_respect', 0) or 0):.0f}",
                f"ST Integrity {float(factors.get('st_integrity', 0) or 0):.0f}",
                f"Structure {float(factors.get('structure', 0) or 0):.0f}",
                f"Participation {float(factors.get('participation', 0) or 0):.0f}",
                f"Efficiency {float(factors.get('efficiency', 0) or 0):.0f}",
            ]
        )
        if factors
        else "Momentum quality unavailable"
    )
    return {
        "Participation": " · ".join(participation),
        "Structure": " · ".join(structure),
        "Momentum Quality": quality_text,
        "Trend Stability": stability_text,
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
    """Rank within a workflow stage by additive Opportunity Score."""
    return (
        float(record.get("opportunity_score_v2", 0) or 0),
    ) + trader_priority_sort_key(record)


_HOT_STATE_RANK = {
    "Entry Ready": 4,
    "Strengthening": 3,
    "Watch List": 2,
    "Candidate": 1,
}


def _hot_state(record: dict) -> str | None:
    """Normalize display states for ranking without changing scanner qualification."""
    state = record.get("candidate_status") or record.get("status")
    if state in {"Entry Ready", "EXCEPTIONAL"}:
        return "Entry Ready"
    if state in {"Strengthening", "ALERT", "WATCH NOW"}:
        return "Strengthening"
    if state in {"Watching", "MONITOR"}:
        return "Watch List"
    if state in {"Emerging", "New"}:
        return "Candidate"
    return None


def _bounded_score(value) -> float:
    return max(0.0, min(100.0, float(value or 0)))


def hot_list_priority_score(record: dict) -> int:
    """Score relative urgency from existing evidence; never qualify a symbol."""
    diagnostics = record.get("participation_surge_diagnostics") or {}
    participation = _bounded_score(
        record.get(
            "participation_surge_score",
            diagnostics.get(
                "participation_score", record.get("participation_score", 0)
            ),
        )
    )
    expansion = _bounded_score(
        record.get("expansion_quality", diagnostics.get("expansion_quality", 0))
    )
    distance = float(
        record.get(
            "vwap_distance_pct",
            (record.get("strengthening_vwap_gate") or {}).get("distance_pct", 0),
        )
        or 0
    )
    # VWAP evidence is strongest close to VWAP and degrades smoothly with distance.
    vwap_quality = max(0.0, 100.0 - abs(distance) * 20.0)
    flow = _bounded_score(
        record.get(
            "dollar_flow_score",
            record.get("market_dominance_score", record.get("attention_score", 0)),
        )
    )
    headline = str(record.get("headline") or "").strip()
    catalyst = float(record.get("catalyst_score", 0) or 0)
    news_age = record.get("news_age_hours")
    fresh_news = bool(headline) and (news_age is None or float(news_age) <= 24)

    # A fresh catalyst is deliberately nonlinear: it can separate two otherwise
    # similar setups, while evidence quality still supplies most of the score.
    catalyst_bonus = (
        15.0 if fresh_news and catalyst >= 0 else (8.0 if headline else 0.0)
    )
    score = participation * 0.35 + expansion * 0.25 + vwap_quality * 0.20
    score += flow * 0.10 + catalyst_bonus
    if distance > 2:
        score -= min(12.0, (distance - 2.0) * 3.0)
    if str(record.get("conviction_trend") or "").lower() in {"falling", "weakening"}:
        score -= 8.0
    if float(record.get("conviction_delta", 0) or 0) < 0:
        score -= min(8.0, abs(float(record.get("conviction_delta", 0))) * 0.4)
    return round(max(0.0, min(100.0, score)))


def _hot_reasons(record: dict) -> list[str]:
    diagnostics = record.get("participation_surge_diagnostics") or {}
    participation = _bounded_score(
        record.get(
            "participation_surge_score",
            diagnostics.get(
                "participation_score", record.get("participation_score", 0)
            ),
        )
    )
    expansion = _bounded_score(
        record.get("expansion_quality", diagnostics.get("expansion_quality", 0))
    )
    distance = float(record.get("vwap_distance_pct", 0) or 0)
    candidates = []
    if participation:
        candidates.append(
            (
                participation,
                f"Participation {'accelerating' if float(record.get('volume_acceleration', 0) or 0) > 1 else 'strong'} ({participation:.0f})",
            )
        )
    if expansion:
        candidates.append((expansion, f"Expansion Quality {expansion:.0f}"))
    if record.get("headline"):
        candidates.append(
            (
                105.0,
                (
                    "Fresh news catalyst"
                    if record.get("news_age_hours") is None
                    or float(record.get("news_age_hours")) <= 24
                    else "News catalyst"
                ),
            )
        )
    if abs(distance) <= 2:
        candidates.append((90.0 - abs(distance) * 10, f"Near VWAP ({distance:+.1f}%)"))
    if (
        max(
            float(record.get("dollar_flow_acceleration_1m", 0) or 0),
            float(record.get("dollar_flow_acceleration_3m", 0) or 0),
            float(record.get("dollar_flow_acceleration_5m", 0) or 0),
        )
        > 1
    ):
        candidates.append((85.0, "Dollar flow increasing"))
    return [label for _, label in sorted(candidates, reverse=True)[:3]]


def _hot_limiter(record: dict) -> str | None:
    distance = float(record.get("vwap_distance_pct", 0) or 0)
    if distance > 2:
        return "VWAP pullback"
    if distance < 0:
        return "VWAP reclaim"
    if float(record.get("conviction_delta", 0) or 0) < 0:
        return "Conviction is cooling"
    if str(record.get("conviction_trend") or "").lower() in {"falling", "weakening"}:
        return "Trend is weakening"
    return None


def _pulse_metric(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return float(value)
    return None


def opportunity_pulse(record: dict) -> dict:
    """Compare display evidence with the prior scan; never change qualification."""
    previous = record.get("opportunity_pulse_previous") or {}
    if not previous:
        return {"label": "STABLE", "color": "yellow", "delta": 0}

    pairs = (
        (
            (_pulse_metric(record, "participation_surge_score", "participation_score")),
            _pulse_metric(previous, "participation_surge_score", "participation_score"),
        ),
        (
            (_pulse_metric(record, "expansion_quality")),
            _pulse_metric(previous, "expansion_quality"),
        ),
        (
            (float(hot_list_priority_score(record))),
            float(hot_list_priority_score(previous)),
        ),
        (
            (_pulse_metric(record, "conviction_v2_score", "conviction_score")),
            _pulse_metric(previous, "conviction_v2_score", "conviction_score"),
        ),
    )
    deltas = [
        current - prior
        for current, prior in pairs
        if current is not None and prior is not None
    ]
    if not deltas:
        return {"label": "STABLE", "color": "yellow", "delta": 0}

    improving = sum(delta > 3 for delta in deltas)
    deteriorating = sum(delta < -3 for delta in deltas)
    major_deterioration = any(delta <= -7 for delta in deltas)
    conviction_delta = pairs[-1][0] - pairs[-1][1] if None not in pairs[-1] else 0
    trend_delta = round(sum(deltas) / len(deltas))
    if deteriorating >= 2 or conviction_delta < -3:
        return {"label": "LOSING MOMENTUM", "color": "red", "delta": trend_delta}
    if improving >= 2 and not major_deterioration:
        return {"label": "ACCELERATING", "color": "green", "delta": trend_delta}
    return {"label": "STABLE", "color": "yellow", "delta": trend_delta}


def walter_hot_list(records: list[dict]) -> list[dict]:
    """Return at most three already-qualified symbols, ordered by state then score."""
    ranked = []
    for record in actionable_candidate_records(records):
        state = _hot_state(record)
        if state is None:
            continue
        ranked.append(
            {
                "symbol": str(record.get("symbol") or "").upper(),
                "state": state,
                "priority_score": hot_list_priority_score(record),
                "pulse": opportunity_pulse(record),
                "reasons": _hot_reasons(record),
                "limiting_factor": _hot_limiter(record),
            }
        )
    ranked.sort(
        key=lambda item: (
            _HOT_STATE_RANK[item["state"]],
            item["priority_score"],
            item["symbol"],
        ),
        reverse=True,
    )
    return ranked[:3]


def _confidence_presentation(score: int) -> tuple[str, str]:
    """Return the display-only confidence label and color for a Priority Score."""
    if score >= 90:
        return "ELITE", "green"
    if score >= 80:
        return "HIGH", "green"
    if score >= 70:
        return "GOOD", "yellow"
    if score >= 60:
        return "DEVELOPING", "yellow"
    return "EARLY", "red"


def render_walter_hot_list(records: list[dict]) -> None:
    """Render the concise three-symbol focus list above the detailed Radar cards."""
    hot = walter_hot_list(records)
    if not hot:
        return
    st.subheader("🔥 Walter's Hot List")
    columns = st.columns(len(hot))
    for rank, (column, item) in enumerate(zip(columns, hot), start=1):
        score = item["priority_score"]
        confidence_label, confidence_color = _confidence_presentation(score)
        confidence_class = f"hot-confidence-{confidence_color}"
        reasons = "".join(
            f"<div class='hot-reason'>✓ {html.escape(reason)}</div>"
            for reason in item["reasons"]
        )
        limiter = item["limiting_factor"]
        pulse = item.get("pulse") or {"label": "STABLE", "color": "yellow", "delta": 0}
        delta = int(pulse["delta"])
        pulse_markup = (
            f"<div class='opportunity-pulse pulse-{pulse['color']}' aria-label='Opportunity pulse: {html.escape(pulse['label'])}, trend {delta:+d}'>"
            f"<span class='pulse-dot' aria-hidden='true'>●</span><span>{html.escape(pulse['label'])}</span>"
            f"<span class='pulse-delta'>{delta:+d}</span></div>"
        )
        needs = (
            f"<div class='hot-heading'>Needs</div><div class='hot-need'>{html.escape(limiter)}</div>"
            if limiter
            else ""
        )
        column.markdown(
            f"<div class='hot-card'><div class='hot-rank'>#{rank} Hot List</div>"
            f"<div class='hot-symbol'>{html.escape(item['symbol'])}</div>"
            f"<div class='hot-confidence'><div class='hot-confidence-title'>Confidence</div>"
            f"<div class='hot-confidence-track' role='progressbar' aria-label='Confidence' "
            f"aria-valuemin='0' aria-valuemax='100' aria-valuenow='{score}'>"
            f"<div class='hot-confidence-fill {confidence_class}' style='--confidence:{score}%'></div></div>"
            f"<div class='hot-confidence-result'><span class='hot-confidence-percent'>{score}%</span>"
            f"<span class='hot-confidence-label {confidence_class}'>{confidence_label}</span></div></div>"
            f"{pulse_markup}"
            f"<div class='hot-heading'>Why Walter likes it</div>{reasons}{needs}</div>",
            unsafe_allow_html=True,
        )


MISSION_BANDS = {
    "trade_soon": ("🟢 OPEN NOW", "#4ade80"),
    "watch_closely": ("🟡 OPENING", "#facc15"),
    "background": ("🔵 MONITOR", "#60a5fa"),
    "ignore": ("🔴 CLOSED", "#f87171"),
}

TRADE_READINESS_STATES = (
    "NOT READY",
    "WATCH",
    "BUILDING",
    "READY",
    "ENTRY WINDOW",
)


def trade_readiness(item: dict) -> dict:
    """Derive a display-only readiness stage from existing state and confidence."""
    record = item["record"]
    state = (
        _hot_state(record)
        or str(record.get("candidate_status") or record.get("status") or "").strip()
    )
    confidence = int(item["confidence"])
    distance = float(record.get("vwap_distance_pct", 0) or 0)
    extended = distance > 2

    if extended:
        index = 1
    elif state == "Entry Ready":
        index = 4
    elif state == "Strengthening":
        index = 3 if confidence >= 75 else 2
    elif state == "Watch List":
        index = 2 if confidence >= 75 else 1
    elif state == "Candidate":
        index = 1 if confidence >= 60 else 0
    else:
        index = 0

    remaining = [
        condition["label"]
        for condition in item["conditions"]
        if not condition["passed"]
    ]
    if extended:
        sentence = "Extended. Wait for pullback."
    elif remaining and remaining[0] == "VWAP":
        sentence = "Waiting for VWAP reclaim."
    elif remaining and remaining[0] == "SuperTrend Flip":
        sentence = "Waiting for trend confirmation."
    elif remaining:
        sentence = "Momentum confirmed. Entry window approaching."
    elif state == "Entry Ready":
        sentence = "Entry conditions aligned."
    else:
        sentence = "Momentum confirmed. Entry window approaching."

    return {
        "index": index,
        "state": TRADE_READINESS_STATES[index],
        "sentence": sentence,
    }


def _trade_readiness_markup(item: dict) -> str:
    readiness = trade_readiness(item)
    colors = ("#64748b", "#60a5fa", "#facc15", "#f59e0b", "#4ade80")
    color = colors[readiness["index"]]
    segments = "".join(
        f"<span class='trade-readiness-step{' is-reached' if index <= readiness['index'] else ''}'></span>"
        for index in range(len(TRADE_READINESS_STATES))
    )
    labels = "".join(
        f"<span class='trade-readiness-label{' is-current' if index == readiness['index'] else ''}'>{label}</span>"
        for index, label in enumerate(TRADE_READINESS_STATES)
    )
    entry_class = " is-entry-window" if readiness["state"] == "ENTRY WINDOW" else ""
    return (
        f"<div class='trade-readiness{entry_class}' style='--readiness-color:{color}' "
        f"role='meter' aria-label='Trade readiness: {readiness['state']}' aria-valuemin='0' "
        f"aria-valuemax='4' aria-valuenow='{readiness['index']}'>"
        f"<div class='trade-readiness-title'>Trade Readiness</div>"
        f"<div class='trade-readiness-track' aria-hidden='true'>{segments}</div>"
        f"<div class='trade-readiness-labels' aria-hidden='true'>{labels}</div>"
        f"<div class='trade-readiness-state'>{readiness['state']}</div>"
        f"<div class='trade-readiness-sentence'>{html.escape(readiness['sentence'])}</div></div>"
    )


def _mission_conditions(record: dict) -> list[dict]:
    """Translate current scanner evidence into Walter's visible setup checklist."""
    relation = str(record.get("vwap_relation") or "").lower()
    distance = float(record.get("vwap_distance_pct", 0) or 0)
    vwap_passed = relation == "above" and distance <= 2
    trend_passed = bool(
        record.get("supertrend_bullish") or record.get("supertrend_flip")
    )
    participation = _bounded_score(
        record.get("participation_surge_score", record.get("participation_score", 0))
    )
    return [
        {"label": "VWAP", "passed": vwap_passed},
        {"label": "SuperTrend Flip", "passed": trend_passed},
        {"label": "Participation > 90", "passed": participation > 90},
    ]


def _mission_band(record: dict, conditions: list[dict]) -> str:
    state = _hot_state(record)
    distance = float(record.get("vwap_distance_pct", 0) or 0)
    if state is None or distance > 5:
        return "ignore"
    remaining = sum(not condition["passed"] for condition in conditions)
    if state == "Entry Ready" and remaining == 0:
        return "trade_soon"
    if state in {"Entry Ready", "Strengthening"}:
        return "watch_closely"
    return "background"


def _mission_status(record: dict, band: str, conditions: list[dict]) -> str:
    if band == "ignore":
        if float(record.get("vwap_distance_pct", 0) or 0) > 5:
            return "Too extended"
        participation = _bounded_score(
            record.get(
                "participation_surge_score", record.get("participation_score", 0)
            )
        )
        if participation < 50:
            return "Low participation"
        expansion = _bounded_score(record.get("expansion_quality", 0))
        if expansion < 50:
            return "Weak expansion"
        return "No actionable setup"
    remaining = [item["label"] for item in conditions if not item["passed"]]
    if not remaining:
        return "Setup conditions aligned — review the chart"
    if remaining[0] == "VWAP":
        return "Wait for VWAP reclaim"
    if remaining[0] == "SuperTrend Flip":
        return "Ready if candle confirms SuperTrend"
    return "Wait for participation above 90"


def _mission_conviction_label(confidence: int) -> tuple[str, str]:
    """Return the compact, display-only readiness label for mission confidence."""
    if confidence > 90:
        return "🟢 GREEN LIGHT", "#4ade80"
    if confidence >= 75:
        return "🟡 BUILDING", "#facc15"
    return "🔵 EARLY", "#60a5fa"


def _mission_conviction_reasons(record: dict) -> list[str]:
    """Select the three strongest existing evidence signals for HUD presentation."""
    previous = record.get("opportunity_pulse_previous") or {}
    participation = _bounded_score(
        record.get("participation_surge_score", record.get("participation_score", 0))
    )
    expansion = _bounded_score(record.get("expansion_quality", 0))
    flow = _bounded_score(
        record.get("dollar_flow_score", record.get("market_dominance_score", 0))
    )
    distance = abs(float(record.get("vwap_distance_pct", 0) or 0))
    headline = str(record.get("headline") or "").strip()
    news_age = record.get("news_age_hours")
    fresh_news = bool(headline) and (news_age is None or float(news_age) <= 24)
    confidence_gain = hot_list_priority_score(record) - (
        hot_list_priority_score(previous)
        if previous
        else hot_list_priority_score(record)
    )
    signals = [
        (participation, "Strongest Participation today"),
        (100 if fresh_news else 0, "Fresh news catalyst"),
        (flow, "Highest dollar flow"),
        (max(0.0, 100 - distance * 20), "Best VWAP structure"),
        (max(0, 50 + confidence_gain * 5), "Fastest improving confidence"),
        (expansion, "Best Expansion Quality"),
    ]
    signals.sort(key=lambda signal: signal[0], reverse=True)
    return [label for _, label in signals[:3]]


def _mission_why_not_primary(item: dict, primary: dict) -> str:
    """Summarize the secondary target's single most important visible gap."""
    distance = float(item["record"].get("vwap_distance_pct", 0) or 0)
    participation = _bounded_score(
        item["record"].get(
            "participation_surge_score", item["record"].get("participation_score", 0)
        )
    )
    if distance > 2:
        return "Slightly extended."
    if not item["conditions"][0]["passed"]:
        return "Waiting for VWAP reclaim."
    if participation < 90:
        return "Needs stronger participation."
    return f"Lower conviction than {primary['symbol']}."


def walter_mission_control(records: list[dict]) -> dict:
    """Commit attention to one primary and one secondary without issuing trades."""
    candidates = []
    ignored = []
    for record in actionable_candidate_records(records):
        conditions = _mission_conditions(record)
        previous_record = record.get("opportunity_pulse_previous") or {}
        band = _mission_band(record, conditions)
        item = {
            "symbol": str(record.get("symbol") or "").upper(),
            "confidence": hot_list_priority_score(record),
            "conviction_trend": record.get("conviction_trend", "→"),
            "ranking_move_reasons": list(record.get("ranking_move_reasons") or []),
            "band": band,
            "status": _mission_status(record, band, conditions),
            "conditions": conditions,
            "previous_conditions": (
                _mission_conditions(previous_record) if previous_record else []
            ),
            "previous_record": previous_record,
            "record": record,
            "reasons": _mission_conviction_reasons(record),
        }
        if band == "ignore":
            ignored.append(item)
        else:
            candidates.append(item)
    # Every record reaching this function has already qualified for the visible
    # watch workflow. Keep the existing mission bands and score ranking, but let
    # a lower-attention band fill an otherwise empty Primary/Secondary slot.
    band_rank = {"trade_soon": 3, "watch_closely": 2, "background": 1, "ignore": 0}
    ranked = candidates + ignored
    ranked.sort(
        key=lambda item: (band_rank[item["band"]], item["confidence"], item["symbol"]),
        reverse=True,
    )
    selected = ranked[:2]
    selected_ids = {id(item) for item in selected}
    return {
        "primary": selected[0] if selected else None,
        "secondary": selected[1] if len(selected) > 1 else None,
        "ignored": [item for item in ignored if id(item) not in selected_ids],
    }


def _mission_target_markup(item: dict, role: str, primary: dict | None = None) -> str:
    remaining = sum(not condition["passed"] for condition in item["conditions"])
    presentation_band = (
        "ignore"
        if item["band"] == "ignore"
        else (
            "trade_soon"
            if remaining == 0
            else ("watch_closely" if remaining <= 2 else "background")
        )
    )
    _, band_color = MISSION_BANDS[presentation_band]
    conviction_label, color = _mission_conviction_label(item["confidence"])
    if item["band"] != "trade_soon":
        if item["confidence"] >= 75:
            conviction_label, color = "🟡 BUILDING", "#facc15"
        elif item["confidence"] >= 60:
            conviction_label, color = "🔵 WATCH", "#60a5fa"
        else:
            conviction_label, color = "🔵 EARLY", "#60a5fa"
    window = (
        "Now"
        if remaining == 0
        else ("2–5 minutes" if remaining == 1 else "5–15 minutes")
    )
    checklist = "".join(
        f"<div class='mission-check'>{index}. {'✓' if condition['passed'] else '□'} {html.escape(condition['label'])}</div>"
        for index, condition in enumerate(item["conditions"], 1)
    )
    reasons = "".join(
        f"<div class='mission-reason'>✓ {html.escape(reason)}</div>"
        for reason in item["reasons"]
    )
    previous = item.get("previous_record") or {}
    previous_confidence = (
        hot_list_priority_score(previous) if previous else item["confidence"]
    )
    delta = item["confidence"] - previous_confidence
    direction = "▲" if delta >= 0 else "▼"
    delta_class = "meter-delta-up" if delta >= 0 else "meter-delta-down"
    just_opened = (
        item["band"] == "trade_soon"
        and bool(previous)
        and _mission_band(previous, _mission_conditions(previous)) != "trade_soon"
    )
    explanation = item["record"].get("decision_explanation") or {}
    narrative = str(explanation.get("decision_narrative") or "No ledger explanation recorded.")
    positive = "; ".join(explanation.get("strongest_positive_factors") or []) or "None recorded."
    negative = "; ".join(explanation.get("strongest_negative_factors") or []) or "None recorded."
    details = [
        f"Strongest positives: {positive}", f"Strongest negatives: {negative}",
        f"Catalyst: {explanation.get('catalyst_summary')}",
        f"Participation: {explanation.get('participation_summary')}",
        f"Expansion: {explanation.get('expansion_summary')}",
        f"Conviction trend: {explanation.get('conviction_trend')}",
        f"Entry readiness: {explanation.get('entry_readiness_summary')}",
        explanation.get("ranking_change_explanation"), explanation.get("why_not_number_one"),
    ]
    explanation_markup = (
        "<div class='decision-narrative'><b>DECISION NARRATIVE</b>"
        + html.escape(narrative)
        + "<br>" + "<br>".join(html.escape(str(value)) for value in details if value)
        + "</div>"
    )
    return (
        f"<div class='mission-target{' entry-window-pulse' if just_opened else ''}' style='--mission-color:{color}'>"
        f"<div class='mission-role'>{role}</div><div class='mission-symbol'>{html.escape(item['symbol'])}</div>"
        f"<div class='mission-band' style='color:{band_color}'>CONVICTION {html.escape(item['conviction_trend'])}</div><div class='mission-window-status'>{conviction_label}</div>"
        f"<div class='opportunity-meter'><div class='opportunity-meter-top'><span class='opportunity-meter-label'>Conviction Meter</span><span class='opportunity-meter-value'>{item['confidence']}% <small class='{delta_class}'>{direction} {delta:+d}</small></span></div>"
        f"<div class='opportunity-meter-track' role='progressbar' aria-label='Conviction meter' aria-valuemin='0' aria-valuemax='100' aria-valuenow='{item['confidence']}'><div class='opportunity-meter-fill' style='--opportunity:{item['confidence']}%'></div></div></div>"
        + _trade_readiness_markup(item)
        + (
            f"<div class='mission-section-title'>WHY #1 TODAY</div><div class='mission-reasons'>{reasons}</div>"
            if primary is None
            else ""
        )
        + f"<div class='mission-section-title'>ENTRY PATH</div><div class='mission-path'>{checklist}</div>"
        + (
            f"<div class='mission-why-not'><b>WHY NOT #1</b>{html.escape(_mission_why_not_primary(item, primary))}</div>"
            if primary is not None
            else ""
        )
        + explanation_markup
        + f"<div class='mission-meta'>Estimated: <b>{window}</b></div></div>"
    )


def render_walter_mission_control(records: list[dict]) -> None:
    """Render Walter's single committed attention plan ahead of dashboard detail."""
    mission = walter_mission_control(records)
    if not mission["primary"]:
        st.markdown(
            "<div class='mission-shell'><div class='mission-title'>🎯 TODAY'S MISSION</div>No stock deserves elevated attention right now.</div>",
            unsafe_allow_html=True,
        )
        return
    selected = [mission["primary"], mission["secondary"]]
    monitoring_markup = ""
    if not any(item and item["band"] == "trade_soon" for item in selected):
        monitoring_markup = (
            "<div class='mission-monitoring'>No entry-ready setups. Continue monitoring.</div>"
        )
    targets = _mission_target_markup(mission["primary"], "Primary target")
    if mission["secondary"]:
        targets += _mission_target_markup(
            mission["secondary"], "Secondary target", mission["primary"]
        )
    ignored = mission["ignored"]
    ignore_markup = ""
    if ignored:
        names = " · ".join(
            f"{html.escape(item['symbol'])} — {html.escape(item['status'])}"
            for item in ignored[:3]
        )
        ignore_markup = (
            f"<div class='mission-ignore'><b>IGNORE TODAY</b> · {names}</div>"
        )
    st.markdown(
        f"<div class='mission-shell'><div class='mission-title'>🎯 TODAY'S MISSION</div>{monitoring_markup}<div class='mission-grid'>{targets}</div>{ignore_markup}</div>",
        unsafe_allow_html=True,
    )


def render_live_opportunity_feed(events: list[dict]) -> None:
    """Render the compact, newest-first mission log beneath Today's Mission."""
    rows = []
    for event in events[:10]:
        color = event.get("color", "yellow")
        marker = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(color, "🟡")
        rows.append(
            "<div class='feed-event'>"
            f"<span class='feed-time'>{html.escape(str(event.get('time', '')))}</span>"
            f"<span class='feed-symbol'>{html.escape(str(event.get('symbol', '')))}</span>"
            f"<span class='feed-message feed-{color}'>{marker} {html.escape(str(event.get('message', '')))}</span>"
            "</div>"
        )
    content = (
        "".join(rows)
        or "<div class='feed-empty'>Waiting for a meaningful change.</div>"
    )
    st.markdown(
        f"<div class='feed-shell'><div class='feed-title'>LIVE OPPORTUNITY FEED</div>{content}</div>",
        unsafe_allow_html=True,
    )


ESCALATION_COLORS = {
    "Entry Window Open": "#4ade80",
    "Watch Closely": "#facc15",
    "Monitor": "#60a5fa",
    "Too Extended": "#f87171",
}

RECOMMENDATION_COLORS = {
    "GREEN LIGHT": "#4ade80",
    "GET READY": "#facc15",
    "NO TRADE": "#f87171",
}


def render_escalation_engine(records: list[dict]) -> None:
    """Render Walter's immediate preparation recommendation and supporting evidence."""
    snapshots = [
        escalation_snapshot(record) for record in actionable_candidate_records(records)
    ]
    if not snapshots:
        st.markdown(
            "<div class='recommendation-box' style='--recommendation-color:#f87171'><div class='recommendation-label'>🔴 NO TRADE</div><div class='recommendation-message'>No setup currently qualifies for preparation.</div></div>",
            unsafe_allow_html=True,
        )
        return
    st.subheader("Walter's Recommendation")
    st.caption("Can I start preparing to buy?")
    for item in snapshots[:5]:
        trend = item["confidence_trend"]
        trend_arrow = {"Rising": "↗", "Falling": "↘", "Steady": "→"}[trend["direction"]]
        checklist = "".join(
            f"<li class='{'delta-up' if check['ready'] else 'delta-down'}'>{'✓' if check['ready'] else '○'} {html.escape(check['label'])}</li>"
            for check in item["checklist"]
        )
        deltas = (
            "".join(
                f"<li class='{'delta-up' if delta['direction'] == 'improved' else 'delta-down'}'>{html.escape(delta['label'])}: {html.escape(delta['display'])}</li>"
                for delta in item["deltas"]
            )
            or "<li class='small'>No meaningful evidence change since the prior scan.</li>"
        )
        color = ESCALATION_COLORS[item["state"]]
        recommendation = item["recommendation"]
        recommendation_color = RECOMMENDATION_COLORS[recommendation["label"]]
        st.markdown(
            f"<div class='recommendation-box' style='--recommendation-color:{recommendation_color}'><div class='recommendation-label'>{recommendation['emoji']} {html.escape(recommendation['label'])}</div><div class='recommendation-message'>{html.escape(recommendation['message'])}</div></div>"
            f"<div class='escalation-card' style='--escalation-color:{color}'><div class='escalation-top'>"
            f"<span class='escalation-symbol'>{html.escape(item['symbol'])}</span><span class='escalation-state'>{html.escape(item['state'])}</span>"
            f"<span class='escalation-trend'>Confidence {trend_arrow} {trend['direction']} ({trend['delta']:+.1f})</span></div>"
            f"<div class='escalation-details'><div><div class='why-label'>Ready checklist</div><ul class='escalation-list'>{checklist}</ul></div>"
            f"<div><div class='why-label'>Since last scan</div><ul class='escalation-list'>{deltas}</ul></div></div></div>",
            unsafe_allow_html=True,
        )


SCANNER_V2_DISPLAY_ORDER = (
    "Entry Ready",
    "Strengthening",
    "Watch List",
    "Weak / Removed",
    "Candidates",
)


def state_sections(records):
    """Group qualified Scanner V2 candidates by trading state for dashboard display."""
    records = actionable_candidate_records(records)
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
        sections[state].sort(key=automatic_watching_sort_key, reverse=True)
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
    if not history:
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
    if (record.get("candidate_status") or record.get("status")) != "Entry Ready":
        pieces.extend(
            [
                "<span class='transition-arrow'>↓</span>",
                "<span class='transition-node trend-pending'>Entry Ready · Pending</span>",
            ]
        )
    return f"<div class='why-label'>History · State progression</div><div class='transition-history'>{''.join(pieces)}</div>"


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
        f"<div class='trend-ladder'><span class='trend-condition'>Now · Trend sequence: {condition}</span>"
        f"{''.join(pieces)}</div>"
    )


def alignment_markup(record: dict) -> str:
    """Render 30s/1m/5m confirmation and its ranking-only score."""
    details = record.get("timeframe_alignment") or {}
    if record.get("alignment_score") is None and not details:
        return ""
    steps = "".join(
        f"<span class='trend-step {'trend-ok' if (details.get(label) or {}).get('aligned') else 'trend-bad'}'>"
        f"{label} {'✓' if (details.get(label) or {}).get('aligned') else '✗'}</span>"
        for label in ("30s", "1m", "5m")
    )
    score = int(record.get("alignment_score", 0) or 0)
    label = html.escape(str(record.get("alignment_label") or "Countertrend"))
    return (
        f"<div class='trend-ladder'><span class='trend-condition'>Alignment {score}/3 · {label} · ranking only</span>"
        f"{steps}</div>"
    )


def trigger_diagnostic_markup(record: dict) -> str:
    """Render Walter's YES/NO trigger decision and exact condition reasons."""
    diagnostic = record.get("trigger_diagnostics") or {}
    trigger = diagnostic.get("trigger") or record.get("trigger")
    if not trigger:
        return ""
    reasons = diagnostic.get("reasons") or record.get("trigger_reasons") or []
    klass = "trigger-yes" if trigger == "YES" else "trigger-no"
    label = "Reason" if trigger == "YES" else "Failed conditions"
    items = "".join(f"<li>• {html.escape(str(reason))}</li>" for reason in reasons)
    if not items:
        items = "<li>• No trigger diagnostics available</li>"
    return (
        f"<div class='trigger-diagnostic {klass}'>"
        f"<div class='trigger-title'>Action · Trigger recommendation = {html.escape(str(trigger))}</div>"
        f"<div class='small'>{label}:</div><ul>{items}</ul></div>"
    )


def _trend_reason_label(reason: str) -> str:
    """Make comparison-based conviction drivers explicit at display time."""
    labels = {
        "Participation faded": "Participation cooling vs previous scan",
        "Participation accelerated": "Participation stronger than previous scan",
        "Dollar flow decreased": "Dollar flow lower than previous scan",
        "Dollar flow increased": "Dollar flow higher than previous scan",
        "Trend confirmation weakened": "Primary trend weaker than previous scan",
        "SuperTrend confirmed": "Primary trend stronger than previous scan",
    }
    return labels.get(reason, f"{reason} vs previous scan")


def opportunity_card(r):
    """Render the five-second trader card; engineering detail lives in Diagnostics."""
    status = r.get("status", "")
    klass = {
        "EXCEPTIONAL": "mide-exceptional",
        "ALERT": "mide-alert",
        "WATCH NOW": "mide-watch",
        "MONITOR": "mide-monitor",
    }.get(status, "")
    if promoted_this_scan(r):
        klass = f"{klass} mide-promoted".strip()

    surge = float(
        r.get(
            "participation_surge_score",
            (r.get("participation_surge_diagnostics") or {}).get(
                "participation_score", 0
            ),
        )
        or 0
    )
    expansion = float(
        r.get(
            "expansion_quality",
            (r.get("participation_surge_diagnostics") or {}).get(
                "expansion_quality", 0
            ),
        )
        or 0
    )
    distance = float(
        r.get(
            "vwap_distance_pct",
            (r.get("strengthening_vwap_gate") or {}).get("distance_pct", 0),
        )
        or 0
    )
    st_bullish = bool(r.get("supertrend_bullish"))
    current_items = [
        (
            "Quality Score",
            f"{r.get('quality_grade', 'Watch Only')} · {int(r.get('quality_score', 0) or 0)} /100",
            float(r.get("quality_score", 0) or 0) >= 75,
            "RANKING ONLY",
        ),
        (
            "RS Score",
            f"{float(r.get('relative_strength_score', 0) or 0):+.1f}%",
            True,
            f"vs {r.get('relative_strength_benchmark', 'SPY')} · RANKING ONLY",
        ),
        (
            "Participation Surge",
            f"{surge:.0f} /100",
            surge >= 72,
            "PASS (≥72)" if surge >= 72 else "FAIL (Requires 72)",
        ),
        (
            "Expansion Quality",
            f"{expansion:.0f} /100",
            expansion >= 58,
            "PASS (≥58)" if expansion >= 58 else "FAIL (Requires 58)",
        ),
        (
            "VWAP Distance",
            f"{distance:+.1f}%",
            0 <= distance <= 2,
            (
                "PASS (0–2%)"
                if 0 <= distance <= 2
                else ("FAIL (Max 2%)" if distance > 2 else "FAIL (Must be above VWAP)")
            ),
        ),
        (
            "SuperTrend",
            "Bullish" if st_bullish else "Not bullish",
            st_bullish,
            "CURRENT STATE",
        ),
    ]
    current_markup = "".join(
        f"<div class='current-item'><div class='score-name'>{html.escape(name)}</div><div class='current-value'>{html.escape(value)}</div><div class='{'threshold-pass' if passed else 'threshold-fail'}'>{html.escape(threshold)}</div></div>"
        for name, value, passed, threshold in current_items
    )

    workflow = str(r.get("workflow_label") or r.get("candidate_status") or status)
    recommendation = trade_recommendation(r)
    action = f"{recommendation['emoji']} {recommendation['label']}"
    why = recommendation["message"]

    evidence = []
    if r.get("headline"):
        evidence.append("News catalyst")
    if float(r.get("volume_acceleration", 0) or 0) > 1:
        evidence.append(
            f"Volume acceleration {float(r['volume_acceleration']):.1f}× (above 1×)"
        )
    if (
        max(
            float(r.get("dollar_flow_acceleration_1m", 0) or 0),
            float(r.get("dollar_flow_acceleration_3m", 0) or 0),
            float(r.get("dollar_flow_acceleration_5m", 0) or 0),
        )
        > 1
    ):
        evidence.append("Dollar flow increasing")
    evidence.append(
        "Above VWAP"
        if r.get("vwap_relation") == "above"
        else "Below VWAP" if r.get("vwap_relation") == "below" else "Testing VWAP"
    )
    evidence.extend(
        [
            "SuperTrend bullish" if st_bullish else "SuperTrend not bullish",
            f"Participation Surge {surge:.0f}/100 ({'PASS ≥72' if surge >= 72 else 'FAIL; requires 72'})",
            f"Expansion Quality {expansion:.0f}/100 ({'PASS ≥58' if expansion >= 58 else 'FAIL; requires 58'})",
        ]
    )
    evidence_markup = "".join(f"<li>✔ {html.escape(item)}</li>" for item in evidence)

    trend_markup = ""
    if "conviction_delta" in r:
        delta = float(r.get("conviction_delta", 0) or 0)
        trend_markup = f"<div class='context-heading'>TREND — compared with previous scan</div><div class='small'>Conviction {delta:+.1f}</div>"
    evaluated = format_eastern_time(r.get("timestamp"), fallback="now")
    st.markdown(
        f"""
    <div class="mide-card {klass}">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <div><span style="font-size:1.55rem;font-weight:800">{html.escape(str(r["symbol"]))}</span>
        <span class="small"> ${r["price"]:.4f} · {r["pct_change"]:+.1f}%</span>
        </div>
        <div style="font-size:1.15rem;font-weight:800">{html.escape(str(workflow))}</div>
      </div>
      <div class="context-heading">NOW — current scan</div>
      <div class="current-grid">{current_markup}</div>
      <div class="context-heading">ACTION — Walter's recommendation</div>
      <div class="action-box">{html.escape(action)}</div>
      <div class="context-heading">WHY</div><div class="why">{html.escape(why)}</div>
      <div class="why-summary"><div class="why-summary-title">Current Evidence</div><ul class="evidence-list">{evidence_markup}</ul></div>
      {alignment_markup(r)}
      {trend_markup}
      <div class="freshness">NOW — evaluated {html.escape(evaluated)}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_calibration_dashboard(report: dict) -> None:
    """Render downstream calibration evidence without returning runtime inputs."""
    st.subheader("Walter Calibration Dashboard")
    st.caption(
        "Measurement only — calibration does not alter ranking, scoring, or qualification."
    )
    ranking = report.get("ranking") or {}
    readiness = report.get("readiness") or {}
    columns = st.columns(3)
    columns[0].metric(
        "Ranking accuracy",
        f"{ranking.get('accuracy'):.1f}%" if ranking.get("accuracy") is not None else "—",
    )
    columns[1].metric(
        "Readiness accuracy",
        f"{readiness.get('accuracy'):.1f}%"
        if readiness.get("accuracy") is not None
        else "—",
    )
    confidence = report.get("rolling_confidence")
    columns[2].metric("Rolling confidence", f"{confidence:.1f}%" if confidence is not None else "—")
    cards = report.get("component_scorecards") or {}
    if cards:
        st.markdown("##### Component accuracy")
        st.dataframe(
            [{"Component": name, **values} for name, values in cards.items()],
            use_container_width=True,
            hide_index=True,
        )
    st.markdown("##### Outcome distribution")
    st.bar_chart(report.get("outcome_distribution") or {})
    weekly = (report.get("weekly") or {}).get("subsystems") or {}
    if weekly:
        st.markdown("##### Rolling subsystem performance")
        st.dataframe(
            [{"Subsystem": name, **values} for name, values in weekly.items()],
            use_container_width=True,
            hide_index=True,
        )
