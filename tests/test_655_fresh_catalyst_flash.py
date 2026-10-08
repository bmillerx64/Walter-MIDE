from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide.gs655_fresh_catalyst_flash import catalyst_flash_rows
from mide.news_provider import NewsArticle


UTC = timezone.utc


def article(article_id, headline, created_at, symbols=("QNME",), source="Benzinga"):
    return NewsArticle(
        id=article_id,
        headline=headline,
        created_at=created_at,
        updated_at=None,
        symbols=list(symbols),
        source=source,
        url=None,
        provider="Alpaca market news",
    )


def test_gs655_surfaces_fresh_material_contract_with_scale():
    now = datetime(2026, 10, 8, 19, 0, tzinfo=UTC)
    rows = catalyst_flash_rows(
        [
            article(
                "q1",
                "Quanome Signs 60-Month AI Infrastructure Services Agreement "
                "Worth More Than $100M, Secures First Enterprise Customer",
                now - timedelta(seconds=45),
            )
        ],
        now=now,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "QNME"
    assert row["event_category"] == "CONTRACT_ORDER"
    assert row["event_label"] == "CONTRACT / ORDER"
    assert "$100M" in row["quantity_label"]
    assert row["age_seconds"] == 45.0
    assert row["authority"] == "NEWS_AWARENESS_ONLY"
    assert row["trading_authority_changed"] is False


def test_gs655_excludes_old_risk_and_roundup_news():
    now = datetime(2026, 10, 8, 19, 0, tzinfo=UTC)
    rows = catalyst_flash_rows(
        [
            article(
                "old",
                "ABC Wins $25 Million Contract Award",
                now - timedelta(minutes=31),
                symbols=("ABC",),
            ),
            article(
                "risk",
                "XYZ Announces $10 Million Registered Direct Offering",
                now - timedelta(minutes=1),
                symbols=("XYZ",),
            ),
            article(
                "roundup",
                "12 Industrials Stocks Moving in Thursday's After-Market Session",
                now - timedelta(seconds=30),
                symbols=("MOVE",),
            ),
        ],
        now=now,
    )

    assert rows == []


def test_gs655_is_freshness_first_and_keeps_one_story_per_symbol():
    now = datetime(2026, 10, 8, 19, 0, tzinfo=UTC)
    rows = catalyst_flash_rows(
        [
            article(
                "older-big",
                "AAA Wins $500 Million Contract Award",
                now - timedelta(minutes=5),
                symbols=("AAA",),
            ),
            article(
                "newer-partner",
                "BBB Announces Strategic Partnership Collaboration",
                now - timedelta(minutes=1),
                symbols=("BBB",),
            ),
            article(
                "aaa-new",
                "AAA Signs New Supply Agreement",
                now - timedelta(minutes=2),
                symbols=("AAA",),
            ),
        ],
        now=now,
    )

    assert [row["symbol"] for row in rows] == ["BBB", "AAA"]
    assert rows[1]["headline"] == "AAA Signs New Supply Agreement"


def test_gs655_rejects_untrusted_source_for_prominent_flash():
    now = datetime(2026, 10, 8, 19, 0, tzinfo=UTC)
    rows = catalyst_flash_rows(
        [
            article(
                "forum",
                "ZZZ Wins $100 Million Contract Award",
                now - timedelta(seconds=10),
                symbols=("ZZZ",),
                source="Random Forum",
            )
        ],
        now=now,
    )
    assert rows == []


def test_gs655_is_wired_beside_persistent_sidebar_audio_health():
    source = Path("app.py").read_text()
    health = source.index("render_sidebar_audio_health(st)")
    flash = source.index("render_fresh_catalyst_sidebar(st, st.session_state)")
    diagnostics = source.index('with st.expander("Diagnostics"', flash)

    assert health < flash < diagnostics
    assert "from mide.gs655_fresh_catalyst_flash import render_fresh_catalyst_sidebar" in source
