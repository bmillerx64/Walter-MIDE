from pathlib import Path


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs636_defers_stale_view_reload_while_voice_is_speaking():
    source = _app_source()

    assert "const voiceTransportSpeaking = now =>" in source
    assert "(synth && synth.speaking)" in source
    assert "transport.status === 'speaking'" in source
    assert "walterVoiceRecoveryDeferral" in source
    assert "now - startedAt < 45_000" in source

    recovery = source.index("if (browserRecoveryDue && recoveryAllowed)")
    deferred = source.index("if (voiceTransportSpeaking(now))", recovery)
    reload_call = source.index("forceTopLevelRecovery();", recovery)

    assert recovery < deferred < reload_call
    assert "VOICE ACTIVE · RECOVERY DEFERRED" in source[deferred:reload_call]


def test_gs636_does_not_change_process_scan_ownership():
    source = _app_source()

    # GS636 protects only the browser-document recovery path. Existing process
    # ownership and scheduler authority remain the same.
    assert "backend process-owned AutoScan continues untouched" in source
    assert "const processOwned =" in source
    assert "const browserRecoveryDue = recoveryDue" in source
