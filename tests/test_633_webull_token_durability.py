from __future__ import annotations

from pathlib import Path

from mide import webull_sdk


class ApiClient:
    def __init__(self):
        self.token_dir = None

    def set_token_dir(self, value):
        self.token_dir = value


def test_persisted_token_secret_is_optional_and_preserves_current_behavior(monkeypatch):
    monkeypatch.delenv("WEBULL_OPENAPI_PERSISTED_TOKEN", raising=False)
    monkeypatch.delenv("WEBULL_OPENAPI_TOKEN_DIR", raising=False)
    client = ApiClient()

    configured, seeded = webull_sdk._seed_persisted_token(client)

    assert configured is False
    assert seeded is False
    assert client.token_dir is None


def test_persisted_token_secret_seeds_sdk_file_before_dataclient_initialization(
    monkeypatch, tmp_path
):
    token = "test-only-persisted-token-value"
    token_dir = tmp_path / "webull-auth"
    monkeypatch.setenv("WEBULL_OPENAPI_PERSISTED_TOKEN", token)
    monkeypatch.setenv("WEBULL_OPENAPI_TOKEN_DIR", str(token_dir))
    client = ApiClient()

    configured, seeded = webull_sdk._seed_persisted_token(client)

    assert configured is True
    assert seeded is True
    assert client.token_dir == str(token_dir)
    lines = (token_dir / "token.txt").read_text(encoding="utf-8").splitlines()
    assert lines == [token, "0", "NORMAL"]


def test_existing_nonempty_sdk_token_wins_over_seed_secret(monkeypatch, tmp_path):
    token_dir = tmp_path / "webull-auth"
    token_dir.mkdir()
    token_file = token_dir / "token.txt"
    token_file.write_text("sdk-refreshed-token\n123456\nNORMAL\n", encoding="utf-8")
    monkeypatch.setenv("WEBULL_OPENAPI_PERSISTED_TOKEN", "older-secret-token")
    monkeypatch.setenv("WEBULL_OPENAPI_TOKEN_DIR", str(token_dir))
    client = ApiClient()

    configured, seeded = webull_sdk._seed_persisted_token(client)

    assert configured is True
    assert seeded is False
    assert token_file.read_text(encoding="utf-8") == (
        "sdk-refreshed-token\n123456\nNORMAL\n"
    )


def test_seeded_token_value_never_enters_logging_source():
    source = Path("mide/webull_sdk.py").read_text(encoding="utf-8")
    helper = source.split("def _seed_persisted_token", 1)[1].split(
        "\ndef create_official_client", 1
    )[0]
    assert "LOGGER." not in helper
    assert "logger." not in helper
    assert "print(" not in helper


def test_gitignore_excludes_webull_sdk_token_material():
    ignored = Path(".gitignore").read_text(encoding="utf-8")
    assert "conf/token.txt" in ignored
    assert ".walter_webull_token/" in ignored


def test_policy_guardrail_treats_persisted_token_as_secret():
    source = Path("scripts/policy_guardrails.py").read_text(encoding="utf-8")
    assert "WEBULL_OPENAPI_PERSISTED_TOKEN" in source


def test_scope_does_not_change_market_or_trading_authority():
    source = Path("mide/webull_sdk.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)



def test_gs645_fresh_authorization_removes_runtime_tokens_and_bypasses_seed_once(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    token_dir = tmp_path / "custom-token-dir"
    token_dir.mkdir()
    default_dir = tmp_path / ".walter_webull_token"
    default_dir.mkdir()
    conf_dir = tmp_path / "conf"
    conf_dir.mkdir()

    for token_file in (
        token_dir / "token.txt",
        default_dir / "token.txt",
        conf_dir / "token.txt",
    ):
        token_file.write_text("expired-token\n0\nNORMAL\n", encoding="utf-8")

    monkeypatch.setenv("WEBULL_OPENAPI_PERSISTED_TOKEN", "durable-but-expired")
    monkeypatch.setenv("WEBULL_OPENAPI_TOKEN_DIR", str(token_dir))
    monkeypatch.setattr(webull_sdk, "_BYPASS_PERSISTED_TOKEN_ONCE", False)

    result = webull_sdk.prepare_fresh_authorization()

    assert result["runtime_token_files_removed"] == 3
    assert result["persisted_seed_bypassed_once"] is True
    assert not (token_dir / "token.txt").exists()
    assert not (default_dir / "token.txt").exists()
    assert not (conf_dir / "token.txt").exists()

    client = ApiClient()
    configured, seeded = webull_sdk._seed_persisted_token(client)
    assert configured is True
    assert seeded is False
    assert client.token_dir == str(token_dir)
    assert not (token_dir / "token.txt").exists()

    # The bypass is exactly one client construction. Ordinary GS633 durability
    # behavior remains intact afterward.
    second = ApiClient()
    configured, seeded = webull_sdk._seed_persisted_token(second)
    assert configured is True
    assert seeded is True
    assert (token_dir / "token.txt").read_text(encoding="utf-8").splitlines() == [
        "durable-but-expired",
        "0",
        "NORMAL",
    ]


def test_gs645_fresh_authorization_does_not_expose_token_material():
    source = Path("mide/webull_sdk.py").read_text(encoding="utf-8")
    helper = source.split("def prepare_fresh_authorization", 1)[1].split(
        "\ndef _consume_fresh_authorization_bypass", 1
    )[0]

    assert "read_text" not in helper
    assert "LOGGER." not in helper
    assert "print(" not in helper
