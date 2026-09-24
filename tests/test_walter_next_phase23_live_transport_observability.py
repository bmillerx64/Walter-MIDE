"""Phase 23: GS481/484/485/486 observability belongs to Replay / Validation."""

from pathlib import Path

from mide import gs481_live_evidence_hard_bind as gs481
from mide import gs484_fmp_transport_truth as gs484
from mide import gs485_retained_news_transport_hard_bind as gs485
from mide import gs486_top_level_transport_truth as gs486
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs481_compatibility_seams_delegate_to_replay_validation():
    # Hot-reload tests may leave a valid prior Replay/Validation generation bound
    # into the facade, so do not require same-generation Python object identity.
    assert gs481._news_truth.__name__ == "live_news_truth"
    assert gs481._stream_failure_truth.__name__ == "stream_failure_truth"
    assert gs481._attach_stream_failure.__name__ == "attach_stream_failure"


def test_gs484_compatibility_seams_delegate_to_replay_validation():
    assert gs484.transport_truth.__name__ == "transport_truth"
    assert gs484._safe_failure.__name__ == "safe_transport_failure"
    assert gs484._latest_article_at.__name__ == "latest_transport_article_at"


def test_gs485_compatibility_seams_delegate_to_replay_validation():
    assert gs485._retained_gs481_globals.__name__ == "retained_gs481_globals"
    assert gs485._wrap_news_truth.__name__ == "wrap_retained_news_truth"


def test_gs486_compatibility_seams_delegate_to_replay_validation():
    assert gs486._news_transport.__name__ == "top_level_news_transport"
    assert gs486._stream_transport.__name__ == "top_level_stream_transport"


def test_phase23_modules_are_facades_not_duplicate_implementations():
    expectations = {
        "mide/gs481_live_evidence_hard_bind.py": (
            "def _news_truth(",
            "def _stream_failure_truth(",
        ),
        "mide/gs484_fmp_transport_truth.py": (
            "def transport_truth(",
            "def _safe_failure(",
        ),
        "mide/gs485_retained_news_transport_hard_bind.py": (
            "def _retained_gs481_globals(",
            "def _wrap_news_truth(",
        ),
        "mide/gs486_top_level_transport_truth.py": (
            "def _news_transport(",
            "def _stream_transport(",
        ),
    }
    for relative, forbidden in expectations.items():
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "mide.authorities import replay_validation as _replay" in source
        for token in forbidden:
            assert token not in source


def test_phase23_stack_remains_observability_only():
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "opportunity_score =",
        "conviction_score =",
        "catalyst_score =",
        "execute_order",
        "place_order",
        "submit_order",
        "requests.get(",
        "requests.post(",
        "ensure_stream(",
        ".subscribe(",
    )
    for relative in (
        "mide/gs481_live_evidence_hard_bind.py",
        "mide/gs484_fmp_transport_truth.py",
        "mide/gs485_retained_news_transport_hard_bind.py",
        "mide/gs486_top_level_transport_truth.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)
