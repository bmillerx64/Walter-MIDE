from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from mide.news import recent_wire_news_log


SETTINGS = SimpleNamespace(
    min_price=0.02, max_price=5.0, min_pct_change=5.0, min_day_volume=100_000
)
NOW = datetime(2026, 7, 28, 15, 0, tzinfo=timezone.utc)


def snapshot(price=1.0, volume=200_000, previous_close=0.9):
    return {
        "latestTrade": {"p": price},
        "latestQuote": {"bp": price - 0.01, "ap": price + 0.01},
        "dailyBar": {"c": price, "v": volume},
        "prevDailyBar": {"c": previous_close},
    }


def test_recent_wire_news_logs_newest_article_and_all_requested_decisions():
    news = [
        {
            "source": "Reuters",
            "created_at": (NOW - timedelta(minutes=80)).isoformat(),
            "headline": "Old contract announcement",
            "symbols": ["PASS"],
        },
        {
            "source": "benzinga",
            "created_at": (NOW - timedelta(minutes=5)).isoformat(),
            "headline": "Company wins FDA approval",
            "symbols": ["PASS", "DROP"],
        },
        {
            "source": "Other Wire",
            "created_at": NOW.isoformat(),
            "headline": "Ignored source",
            "symbols": ["OTHER"],
        },
    ]
    pass_record = {
        "symbol": "PASS",
        "candidate_status": "Strengthening",
        "participation_gate": {"passed": True},
        "expansion_quality": 70,
    }

    rows = recent_wire_news_log(
        news,
        snapshots={"PASS": snapshot(), "DROP": snapshot(price=8)},
        analyzed=[pass_record],
        records=[pass_record],
        settings=SETTINGS,
        now=NOW,
    )

    assert [row["Ticker"] for row in rows] == ["DROP", "PASS"]
    assert rows[0]["Prefilter"] == "FAIL"
    assert rows[0]["Final state"] == "Ignored"
    assert "outside" in rows[0]["Reason if rejected"]
    assert rows[1] == {
        "Ticker": "PASS",
        "News source": "Benzinga",
        "News timestamp": (NOW - timedelta(minutes=5)).isoformat(),
        "News score": 30,
        "Prefilter": "PASS",
        "Participation": "PASS",
        "Expansion": "PASS",
        "Final state": "Strengthening",
        "Reason if rejected": None,
    }


def test_recent_wire_news_excludes_articles_older_than_ninety_minutes():
    rows = recent_wire_news_log(
        [
            {
                "author": "Reuters News",
                "created_at": (NOW - timedelta(minutes=91)).isoformat(),
                "headline": "Contract",
                "symbols": ["OLD"],
            }
        ],
        snapshots={},
        analyzed=[],
        records=[],
        settings=SETTINGS,
        now=NOW,
    )

    assert rows == []
