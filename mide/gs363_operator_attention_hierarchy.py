"""GS363: make Walter's operator priority visible and audible at a glance.

Presentation/alert only.  This module does not change discovery, market data,
scoring inputs, qualification, thresholds, readiness, execution, orders, or
candidate membership.  It sorts trader-facing records by the already-computed
unified opportunity state, then by Walter's existing 0-100 display urgency score.
It also makes high-attention alerts acoustically distinct by repeating the
existing chime: one chime for routine changes, two for LOOK NOW, and three for
WATCH FOR ENTRY / entry-ready states.  Spoken alert phrases are unchanged.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

from .gs310_unified_opportunity_state import (
    CHASE_WAIT,
    DEVELOPING,
    HALTED,
    LOOK_NOW,
    WATCH_FOR_ENTRY,
    opportunity_state,
)


STATE_PRIORITY = {
    WATCH_FOR_ENTRY: 5,
    LOOK_NOW: 4,
    DEVELOPING: 3,
    CHASE_WAIT: 2,
    HALTED: 1,
}
MAX_OPERATOR_ROWS = 5


def operator_attention_score(record: dict) -> int:
    """Return Walter's existing display-only 0-100 urgency score."""
    try:
        from . import ui

        value = int(ui.hot_list_priority_score(record))
    except Exception:
        value = 0
    return max(0, min(100, value))


def operator_display_sort_key(record: dict) -> tuple[int, int, str]:
    """Sort highest-actionability state first, then highest attention score."""
    state = opportunity_state(record)["state"]
    return (
        -int(STATE_PRIORITY.get(state, 0)),
        -operator_attention_score(record),
        str(record.get("symbol") or "").upper(),
    )


def sorted_operator_records(records: list[dict]) -> list[dict]:
    """Return a presentation-only copy ordered for fast operator triage."""
    return sorted(list(records or []), key=operator_display_sort_key)


def alert_chime_count(phrase: str) -> int:
    """Map spoken state text to an acoustic attention tier."""
    text = str(phrase or "").upper()
    if any(
        token in text
        for token in ("WATCH FOR ENTRY", "ENTRY READY", "ENTRY WINDOW", "GET READY")
    ):
        return 3
    if "LOOK NOW" in text or "WATCH NOW" in text:
        return 2
    return 1


def priority_queue_markup(records: list[dict]) -> str:
    """Render the quick-glance ranked queue using existing state and urgency data."""
    from . import ui

    actionable = ui.actionable_candidate_records(records or [])
    visible = sorted_operator_records(actionable)[:MAX_OPERATOR_ROWS]
    if not visible:
        return ""

    rows = []
    for index, record in enumerate(visible, start=1):
        view = opportunity_state(record)
        symbol = html.escape(str(record.get("symbol") or "").upper())
        score = operator_attention_score(record)
        state = html.escape(str(view["state"]))
        color = str(view["color"])
        try:
            pct = float(record.get("pct_change", record.get("percent_change", 0)) or 0)
            pct_text = f"{pct:+.1f}%"
        except (TypeError, ValueError):
            pct_text = ""
        rows.append(
            "<div class='gs363-row'>"
            f"<div class='gs363-rank'>#{index}</div>"
            f"<div class='gs363-symbol'>{symbol}</div>"
            f"<div class='gs363-score'>{score}<span>/100</span></div>"
            f"<div class='gs363-state' style='color:{color}'>{state}</div>"
            f"<div class='gs363-move'>{html.escape(pct_text)}</div>"
            "</div>"
        )

    return (
        "<style>"
        ".gs363-shell{background:#0b1119;border:1px solid #334155;border-left:5px solid #facc15;border-radius:12px;padding:10px 14px;margin:-2px 0 12px}"
        ".gs363-title{font-size:.78rem;letter-spacing:.12em;font-weight:950;color:#f8fafc;margin-bottom:3px}"
        ".gs363-sub{font-size:.78rem;color:#94a3b8;margin-bottom:5px}"
        ".gs363-row{display:grid;grid-template-columns:38px minmax(70px,.65fr) 92px minmax(130px,1fr) 70px;gap:8px;align-items:center;border-top:1px solid #1e293b;padding:6px 0}"
        ".gs363-rank{color:#64748b;font-size:.78rem;font-weight:900}.gs363-symbol{font-size:1rem;font-weight:950;color:#f8fafc}"
        ".gs363-score{font-size:1.18rem;font-weight:950;color:#f8fafc;font-variant-numeric:tabular-nums}.gs363-score span{font-size:.68rem;color:#94a3b8;margin-left:2px}"
        ".gs363-state{font-size:.8rem;font-weight:950;letter-spacing:.04em}.gs363-move{font-size:.8rem;color:#cbd5e1;text-align:right}"
        ".gs363-legend{border-top:1px solid #1e293b;margin-top:2px;padding-top:6px;font-size:.73rem;color:#94a3b8}"
        "@media(max-width:800px){.gs363-row{grid-template-columns:32px 1fr 80px 1fr}.gs363-move{display:none}}"
        "</style>"
        "<div class='gs363-shell'>"
        "<div class='gs363-title'>OPERATOR PRIORITY · HIGH TO LOW</div>"
        "<div class='gs363-sub'>State first, then Walter attention score. Attention is a display cue, not a trade authorization.</div>"
        + "".join(rows)
        + "<div class='gs363-legend'>🔔 WATCH FOR ENTRY = 3 chimes · LOOK NOW = 2 chimes · other state change = 1 chime</div>"
        "</div>"
    )


def _extra_chime_markup(sound_path: str, extra_chimes: int) -> str:
    """Replay the existing chime after the normal alert without duplicating speech."""
    if extra_chimes <= 0:
        return ""
    path = Path(sound_path)
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"""
<audio id="walter-gs363-chime" preload="auto">
  <source src="data:audio/wav;base64,{encoded}" type="audio/wav">
</audio>
<script>
(() => {{
  const audio = document.getElementById('walter-gs363-chime');
  if (!audio) return;
  let remaining = {int(extra_chimes)};
  const playNext = () => {{
    if (remaining <= 0) return;
    remaining -= 1;
    try {{
      audio.currentTime = 0;
      const promise = audio.play();
      if (promise && promise.catch) promise.catch(() => {{}});
    }} catch (_) {{}}
  }};
  audio.addEventListener('ended', () => {{
    if (remaining > 0) window.setTimeout(playNext, 120);
  }});
  const start = () => {{
    const firstChimeMs = Math.max(350, Math.round((audio.duration || 0.6) * 1000) + 120);
    window.setTimeout(playNext, firstChimeMs);
  }};
  if (audio.readyState >= 1) start();
  else audio.addEventListener('loadedmetadata', start, {{once:true}});
}})();
</script>
"""


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_developing_order() -> None:
    """Make the moved Developing summary/detail use the same visible ranking."""
    from . import gs349_operator_first_layout as layout
    from . import ui

    if getattr(layout.developing_records, "_gs363_operator_attention", False):
        return

    def developing_records(records: list[dict]) -> list[dict]:
        rows: list[dict] = []
        developing, _remaining = layout.operator_first_sections(records)
        for _title, section_rows, _expanded in developing:
            rows.extend(section_rows)
        return sorted_operator_records(rows)[: layout.MAX_DEVELOPING_ROWS]

    developing_records._gs363_operator_attention = True
    layout.developing_records = developing_records

    def render_developing_detail(records: list[dict]) -> None:
        developing, _remaining = layout.operator_first_sections(records)
        for section_name, section_records, expanded in developing:
            if not section_records:
                continue
            with ui.st.expander(
                f"{str(section_name).upper()} ({len(section_records)})", expanded=expanded
            ):
                ordered = sorted_operator_records(section_records)
                for record in ordered[:10]:
                    ui.opportunity_card(record)
                ui.st.dataframe(ui.radar_table(ordered), width="stretch", hide_index=True)

    render_developing_detail._gs363_operator_attention = True
    layout.render_developing_detail = render_developing_detail


def install() -> None:
    """Install the final operator-facing sort, numeric cue, and chime hierarchy."""
    from . import ui

    _install_developing_order()

    current_render = ui.render_walter_mission_control
    if not getattr(current_render, "_gs363_operator_attention", False):
        def render_operator_priority(records: list[dict]) -> None:
            ordered = sorted_operator_records(records)
            markup = priority_queue_markup(ordered)
            if markup:
                ui.st.markdown(markup, unsafe_allow_html=True)
            return current_render(ordered)

        _inherit(render_operator_priority, current_render)
        render_operator_priority._gs363_operator_attention = True
        render_operator_priority._gs363_original = current_render
        ui.render_walter_mission_control = render_operator_priority

    current_play_alert = ui.play_alert
    if not getattr(current_play_alert, "_gs363_operator_attention", False):
        def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
            result = current_play_alert(sound_path, phrase, voice_name)
            chimes = alert_chime_count(phrase)
            if chimes > 1:
                markup = _extra_chime_markup(sound_path, chimes - 1)
                if markup:
                    ui.st.components.v1.html(markup, height=0, scrolling=False)
            return result

        _inherit(play_alert, current_play_alert)
        play_alert._gs363_operator_attention = True
        play_alert._gs363_original = current_play_alert
        ui.play_alert = play_alert
