from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


TARGET_RUNTIME = "python-3.13"
SDK_PACKAGE = "webull-openapi-python-sdk"
SDK_APPROVAL_LABEL = "approved-sdk-upgrade"
PROVIDER_GUARD_FILES = {
    "app.py",
    "mide/market_data_providers.py",
    "mide/webull_connection.py",
    "mide/webull_live.py",
}
SECRET_NAMES = ("WEBULL_APP_KEY", "WEBULL_APP_SECRET")
LOG_SINK = re.compile(
    r"\b(?:print|logging\.(?:debug|info|warning|error|exception|critical)|"
    r"logger\.(?:debug|info|warning|error|exception|critical)|"
    r"LOGGER\.(?:debug|info|warning|error|exception|critical)|"
    r"st\.(?:write|text|caption|code|markdown))\s*\("
)


@dataclass(frozen=True)
class DiffLine:
    path: str
    line_no: int
    text: str


def parse_pinned_requirement(text: str, package: str = SDK_PACKAGE) -> str | None:
    pattern = re.compile(rf"^{re.escape(package)}==([^\s#]+)\s*$", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1) if match else None


def runtime_violations(runtime_text: str) -> list[str]:
    if runtime_text.splitlines() != [TARGET_RUNTIME]:
        return [
            f"runtime.txt must contain exactly '{TARGET_RUNTIME}'. "
            "Revert the runtime change unless this PR is an explicit runtime migration."
        ]
    return []


def sdk_pin_violations(
    requirements_text: str,
    *,
    event_name: str,
    labels: tuple[str, ...] = (),
    base_requirements_text: str | None = None,
) -> list[str]:
    current_version = parse_pinned_requirement(requirements_text)
    if current_version is None:
        return [
            f"requirements.txt must keep {SDK_PACKAGE} pinned with '=='. "
            "Restore the exact pin or document and approve the SDK migration."
        ]

    if event_name != "pull_request":
        return []

    if base_requirements_text is None:
        return [
            "Unable to read base-branch requirements.txt for SDK comparison. "
            "Fetch the PR base commit or rerun the workflow."
        ]

    base_version = parse_pinned_requirement(base_requirements_text)
    if base_version is None:
        return [
            f"Base branch requirements.txt does not pin {SDK_PACKAGE}. "
            "Add the exact pin on main before changing it here."
        ]

    if current_version != base_version and SDK_APPROVAL_LABEL not in labels:
        return [
            f"{SDK_PACKAGE} changed from {base_version} to {current_version}. "
            f"Restore the pin or add the '{SDK_APPROVAL_LABEL}' label to an approved SDK upgrade PR."
        ]

    return []


def provider_fallback_violations(added_lines: list[DiffLine]) -> list[str]:
    violations: list[str] = []
    for line in added_lines:
        if line.path not in PROVIDER_GUARD_FILES:
            continue
        lowered = line.text.lower()
        if line.path in {"mide/webull_live.py", "mide/webull_connection.py"} and "alpaca" in lowered:
            violations.append(
                f"{line.path}:{line.line_no} adds an Alpaca reference inside the Live Webull path. "
                "Live Webull mode must remain Webull-only."
            )
            continue
        if line.path == "mide/market_data_providers.py" and (
            ("fallback" in lowered and "alpaca" in lowered)
            or ("alpaca" in lowered and "webull" in lowered)
        ):
            violations.append(
                f"{line.path}:{line.line_no} looks like new Alpaca fallback logic for Webull. "
                "Keep provider substitution explicit and out of the Live Webull path."
            )
            continue
        if line.path == "app.py" and "alpaca" in lowered and "webull" in lowered and any(
            token in lowered for token in ("fallback", "except", "if not", " or ")
        ):
            violations.append(
                f"{line.path}:{line.line_no} looks like Live Webull fallback logic. "
                "Do not silently substitute Alpaca when Webull fails."
            )
    return violations


def secret_logging_violations(added_lines: list[DiffLine]) -> list[str]:
    violations: list[str] = []
    for line in added_lines:
        if not line.path.endswith(".py"):
            continue
        if not any(secret in line.text for secret in SECRET_NAMES):
            continue
        if not LOG_SINK.search(line.text):
            continue
        if not any(token in line.text for token in ("%s", "%r", ".format(", "{", ",")):
            continue
        violations.append(
            f"{line.path}:{line.line_no} appears to log or print a Webull secret value. "
            "Report presence/source only; never emit secret contents."
        )
    return violations


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def load_base_requirements(base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    try:
        return git_output("show", f"{base_ref}:requirements.txt")
    except subprocess.CalledProcessError:
        return None


def load_added_lines(base_ref: str | None, head_ref: str | None) -> list[DiffLine]:
    if not base_ref or not head_ref:
        return []
    diff_text = git_output("diff", "--no-color", "--unified=0", base_ref, head_ref)
    path = ""
    next_line_number = 0
    added: list[DiffLine] = []
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ b/"):
            path = raw_line[6:]
            continue
        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)", raw_line)
            next_line_number = int(match.group(1)) if match else 0
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added.append(DiffLine(path=path, line_no=next_line_number, text=raw_line[1:]))
            next_line_number += 1
    return added


def load_event(event_path: Path) -> dict:
    return json.loads(event_path.read_text(encoding="utf-8"))


def diff_refs(event_name: str, payload: dict) -> tuple[str | None, str | None]:
    if event_name == "pull_request":
        pull_request = payload.get("pull_request") or {}
        return (
            (((pull_request.get("base") or {}).get("sha"))),
            (((pull_request.get("head") or {}).get("sha"))),
        )
    if event_name == "push":
        before = payload.get("before")
        after = payload.get("after")
        if before == "0" * 40:
            return None, after
        return before, after
    return None, None


def labels_from_event(payload: dict) -> tuple[str, ...]:
    pull_request = payload.get("pull_request") or {}
    return tuple(
        label.get("name", "")
        for label in pull_request.get("labels") or []
        if label.get("name")
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enforce Walter-MIDE policy guardrails.")
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-path", required=True)
    args = parser.parse_args(argv)

    payload = load_event(Path(args.event_path))
    labels = labels_from_event(payload)
    base_ref, head_ref = diff_refs(args.event_name, payload)
    runtime_text = Path("runtime.txt").read_text(encoding="utf-8")
    requirements_text = Path("requirements.txt").read_text(encoding="utf-8")
    base_requirements_text = load_base_requirements(base_ref)
    added_lines = load_added_lines(base_ref, head_ref)

    violations = [
        *runtime_violations(runtime_text),
        *sdk_pin_violations(
            requirements_text,
            event_name=args.event_name,
            labels=labels,
            base_requirements_text=base_requirements_text,
        ),
        *provider_fallback_violations(added_lines),
        *secret_logging_violations(added_lines),
    ]

    if violations:
        for violation in violations:
            print(f"::error::{violation}")
        return 1

    print("Policy guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
