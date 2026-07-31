from mide.credentials import credential_diagnostics, load_credentials


def test_credentials_follow_precedence_and_diagnostics_are_redacted(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("WEBULL_APP_KEY=dotenv-key\nWEBULL_APP_SECRET=dotenv-secret\n")
    monkeypatch.setenv("WALTER_ENV", "development")
    monkeypatch.setenv("WEBULL_APP_KEY", "environment-key")

    credentials = load_credentials(
        ("WEBULL_APP_KEY", "WEBULL_APP_SECRET"),
        secrets={"WEBULL_APP_KEY": "streamlit-key"},
        dotenv_path=dotenv,
    )

    assert credentials["WEBULL_APP_KEY"].value == "streamlit-key"
    assert credentials["WEBULL_APP_KEY"].source == "Streamlit Secrets"
    assert credentials["WEBULL_APP_SECRET"].value == "dotenv-secret"
    diagnostics = " ".join(credential_diagnostics(credentials))
    assert "present" in diagnostics
    assert "streamlit-key" not in diagnostics
    assert "dotenv-secret" not in diagnostics


def test_dotenv_is_ignored_outside_explicit_development(monkeypatch, tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("WEBULL_APP_KEY=must-not-load\n")
    monkeypatch.delenv("WALTER_ENV", raising=False)
    monkeypatch.delenv("WEBULL_APP_KEY", raising=False)

    credential = load_credentials(("WEBULL_APP_KEY",), dotenv_path=dotenv)["WEBULL_APP_KEY"]

    assert not credential.present
    assert credential.source == "not configured"
