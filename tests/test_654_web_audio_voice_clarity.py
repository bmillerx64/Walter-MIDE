from pathlib import Path
from types import SimpleNamespace
import hashlib

from mide import gs311_unified_voice as voice


def test_gs654_espeak_clarity_profile(monkeypatch):
    voice._synthesize_phrase_wav.cache_clear()
    calls = []

    monkeypatch.setattr(
        voice.shutil,
        "which",
        lambda name: "/usr/bin/espeak" if name == "espeak" else None,
    )

    def fake_run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=b"RIFF" + b"\x00" * 64)

    monkeypatch.setattr(voice.subprocess, "run", fake_run)

    voice._synthesize_phrase_wav("Ticker S. O. A. R. developing.")

    args = calls[0]
    assert args[args.index("-s") + 1] == "140"
    assert args[args.index("-p") + 1] == "42"
    assert args[args.index("-a") + 1] == "200"
    assert args[args.index("-g") + 1] == "4"
    voice._synthesize_phrase_wav.cache_clear()


def test_gs654_ticker_letters_are_explicitly_separated():
    assert (
        voice._compact_guard_phrase("SOAR. DEVELOPING.")
        == "Ticker S. O. A. R. developing."
    )
    assert (
        voice._compact_guard_phrase("JZ. LOOK NOW.")
        == "Ticker J. Z. look now."
    )


def test_gs654_audio_key_busts_warm_guard_buffer_cache(monkeypatch):
    monkeypatch.setattr(voice, "_synthesize_phrase_wav", lambda phrase: "UklGRg==")
    compact = "Ticker S. O. A. R. developing."
    expected = hashlib.sha1(
        f"{voice.VOICE_ASSET_VERSION}|{compact}".encode("utf-8")
    ).hexdigest()[:16]

    markup = voice._speech_component("", "SOAR. DEVELOPING.")

    assert voice.VOICE_ASSET_VERSION == "GS654"
    assert expected in markup


def test_gs654_scope_is_voice_presentation_only():
    source = Path("mide/gs311_unified_voice.py").read_text(encoding="utf-8")
    clarity_start = source.index('VOICE_ASSET_VERSION = "GS654"')
    assert "place_order(" not in source[clarity_start:]
    assert "submit_order(" not in source[clarity_start:]
