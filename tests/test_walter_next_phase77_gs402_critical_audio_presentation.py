"""Phase 77: GS402 critical-only browser audio belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs367_browser_audio_broker as broker
from mide import gs402_critical_only_audio as gs402
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase77_authority_preserves_exact_gs402_silence_markup():
    base = (
        "    broker.tier = 0;\n\n"
        "    const AudioContextCtor = host.AudioContext;\n"
    )
    markup = presentation_audio.critical_only_audio_markup(base)

    assert "GS402: routine tier remains semantically valid" in markup
    assert "if (tier === 1) return;" in markup
    assert markup.index("if (tier === 1) return;") < markup.index(
        "const AudioContextCtor ="
    )


def test_phase77_legacy_helper_delegates_lazily(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "critical_only_audio_markup",
        lambda _markup: "AUTHORITY",
    )
    assert gs402._critical_only_markup("legacy") == "AUTHORITY"


def test_phase77_installer_preserves_historical_lineage(monkeypatch):
    def baseline(scan_token: str, tier: int) -> str:
        return (
            "    broker.tier = 0;\n\n"
            "    const AudioContextCtor = host.AudioContext;\n"
        )

    monkeypatch.setattr(
        broker,
        "browser_broker_markup",
        baseline,
    )
    presentation_audio.install_critical_only_audio()
    installed = broker.browser_broker_markup

    assert installed is not baseline
    assert getattr(
        installed,
        "_gs402_critical_only_audio",
        False,
    ) is True
    assert getattr(
        installed,
        "_gs402_original",
        None,
    ) is baseline
    assert "if (tier === 1) return;" in installed("scan", 1)

    presentation_audio.install_critical_only_audio()
    assert broker.browser_broker_markup is installed


def test_phase77_stale_presentation_generation_preserves_local_fallback(monkeypatch):
    def baseline(scan_token: str, tier: int) -> str:
        return (
            "    broker.tier = 0;\n\n"
            "    const AudioContextCtor = host.AudioContext;\n"
        )

    monkeypatch.setattr(
        gs402,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        broker,
        "browser_broker_markup",
        baseline,
    )

    gs402.install()
    installed = broker.browser_broker_markup
    assert installed is not baseline
    assert getattr(
        installed,
        "_gs402_critical_only_audio",
        False,
    ) is True
    assert "if (tier === 1) return;" in installed("scan", 1)


def test_phase77_markup_remains_compatible_with_gs418_restore_contract():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    legacy_418 = (
        ROOT / "mide/gs418_restore_routine_scan_audio.py"
    ).read_text(encoding="utf-8")

    assert (
        "GS402: routine tier remains semantically valid but is acoustically silent."
        in authority
    )
    assert "_GS402_SILENCE" in legacy_418
    assert "if (tier === 1) return;" in authority


def test_phase77_audio_meaning_lives_in_presentation_audio():
    legacy = (
        ROOT / "mide/gs402_critical_only_audio.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    assert "def critical_only_audio_markup(" in authority
    assert "def install_critical_only_audio(" in authority
    assert '"critical_only_audio_markup"' in legacy
    assert '"install_critical_only_audio"' in legacy


def test_phase77_scope_is_presentation_audio_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS402 critical-only browser audio")
    end = source.index("# GS457 maturation-leader presentation semantics", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)
