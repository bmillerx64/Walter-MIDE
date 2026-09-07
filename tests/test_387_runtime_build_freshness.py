from mide import version


def _build(loaded="aaaaaaaaaaaa"):
    return version.BuildInfo(
        version="3.0.0",
        built_at="2026-09-07T00:00:00+00:00",
        loaded_git_sha=loaded,
    )


def test_matching_checkout_keeps_normal_build_label(monkeypatch):
    monkeypatch.setattr(version, "_checkout_git_sha", lambda: "aaaaaaaaaaaa")
    build = _build()

    assert build.runtime_stale is False
    assert build.git_sha == "aaaaaaaaaaaa"
    assert build.freshness() == {
        "loaded_git_sha": "aaaaaaaaaaaa",
        "checkout_git_sha": "aaaaaaaaaaaa",
        "runtime_stale": False,
        "status": "CURRENT",
    }


def test_advanced_checkout_makes_stale_runtime_visible(monkeypatch):
    monkeypatch.setattr(version, "_checkout_git_sha", lambda: "bbbbbbbbbbbb")
    build = _build()

    assert build.runtime_stale is True
    assert build.git_sha == "aaaaaaaaaaaa ⚠ RESTART→bbbbbbbbbbbb"
    assert build.freshness()["status"] == "STALE_RUNTIME"


def test_unknown_checkout_never_claims_a_stale_runtime(monkeypatch):
    monkeypatch.setattr(version, "_checkout_git_sha", lambda: "unknown")
    build = _build()

    assert build.runtime_stale is False
    assert build.git_sha == "aaaaaaaaaaaa"
    assert build.freshness()["status"] == "CURRENT"


def test_unknown_loaded_sha_never_claims_a_stale_runtime(monkeypatch):
    monkeypatch.setattr(version, "_checkout_git_sha", lambda: "bbbbbbbbbbbb")
    build = _build("unknown")

    assert build.runtime_stale is False
    assert build.git_sha == "unknown"


def test_runtime_detector_is_observational_only_and_does_not_mutate_checkout(monkeypatch):
    calls = []

    def checkout():
        calls.append("read")
        return "bbbbbbbbbbbb"

    monkeypatch.setattr(version, "_checkout_git_sha", checkout)
    build = _build()

    assert build.runtime_stale is True
    assert build.git_sha.endswith("RESTART→bbbbbbbbbbbb")
    assert calls == ["read", "read"]
