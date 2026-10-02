from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mide.authorities.presentation_audio import catalyst_brief_table


def test_catalyst_brief_prioritizes_time_ticker_headline_columns():
    report = {
        "clusters": [
            {
                "published_at": datetime(2026, 10, 2, 13, 17, tzinfo=timezone.utc),
                "symbol": "ADM",
                "headline": "Example headline",
                "event_category": "PARTNERSHIP_EXPANSION",
                "news_class": "MATERIAL CATALYST",
                "confirmations": 1,
                "sources": ["benzinga"],
            }
        ]
    }

    row = catalyst_brief_table(report)[0]
    assert list(row) == [
        "Time ET",
        "Ticker",
        "Headline",
        "Event",
        "Class",
        "Confirmations",
        "Sources",
    ]


def test_catalyst_brief_render_keeps_headline_large_and_secondary_fields_rightward():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("rows = catalyst_brief_table(report)")
    end = source.index(
        'with st.expander("Catalyst details / corroborating headlines"',
        start,
    )
    block = source[start:end]
    assert '"Time ET": st.column_config.TextColumn(width="small")' in block
    assert '"Ticker": st.column_config.TextColumn(width="small")' in block
    assert '"Headline": st.column_config.TextColumn(width="large")' in block
    assert '"Confirmations": st.column_config.NumberColumn(width="small")' in block


def test_gs630_is_presentation_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("def catalyst_brief_table")
    end = source.index("def catalyst_brief_provider_caption", start)
    block = source[start:end]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in block for token in forbidden)
