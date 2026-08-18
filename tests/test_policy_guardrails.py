from pathlib import Path

from scripts.policy_guardrails import (
    DiffLine,
    SDK_APPROVAL_LABEL,
    provider_fallback_violations,
    runtime_violations,
    sdk_pin_violations,
    secret_logging_violations,
)


def test_runtime_guard_requires_exact_python_313_pin():
    assert runtime_violations("python-3.13\n") == []
    assert runtime_violations("python-3.12\n")


def test_sdk_upgrade_requires_explicit_approval_label():
    base = "webull-openapi-python-sdk==2.0.16\n"
    changed = "webull-openapi-python-sdk==2.0.17\n"
    assert sdk_pin_violations(
        changed,
        event_name="pull_request",
        base_requirements_text=base,
    )
    assert sdk_pin_violations(
        changed,
        event_name="pull_request",
        base_requirements_text=base,
        labels=(SDK_APPROVAL_LABEL,),
    ) == []


def test_provider_fallback_guard_flags_new_alpaca_reference_in_live_webull_path():
    violations = provider_fallback_violations(
        [DiffLine("mide/webull_live.py", 42, "client = AlpacaProvider(key, secret)")]
    )
    assert violations
    assert "Webull-only" in violations[0]


def test_secret_logging_guard_flags_interpolated_webull_secret_output():
    violations = secret_logging_violations(
        [
            DiffLine(
                "app.py",
                101,
                'LOGGER.info(f"WEBULL_APP_SECRET={resolved[\'WEBULL_APP_SECRET\'].value}")',
            )
        ]
    )
    assert violations


def test_guardrail_files_are_tracked_in_repo_contract():
    policy = Path("docs/AGENT_POLICY.md").read_text(encoding="utf-8")
    template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/policy-guardrails.yml").read_text(encoding="utf-8")
    assert "source of truth" in policy
    assert "Live Webull mode must remain Webull-only" in policy
    assert "runtime.txt" in policy
    assert "No silent provider fallback was introduced." in template
    assert "runtime.txt` remains `python-3.13`" in template
    assert "Risk / Rollback" in template
    assert "pull_request" in workflow
    assert "branches:" in workflow
    assert "python-version: '3.13'" in workflow
    assert "approved-sdk-upgrade" in workflow or "approved-sdk-upgrade" in Path(
        "scripts/policy_guardrails.py"
    ).read_text(encoding="utf-8")
    assert "scripts/policy_guardrails.py" in workflow
