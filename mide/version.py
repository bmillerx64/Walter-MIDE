"""The single authoritative source of Walter build identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess


def _version() -> str:
    return (Path(__file__).parents[1] / "VERSION").read_text().strip()


def _git_sha() -> str:
    configured = os.getenv("GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")
    if configured:
        return configured[:12]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=Path(__file__).parents[1], text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


@dataclass(frozen=True)
class BuildInfo:
    version: str
    built_at: str
    git_sha: str


BUILD = BuildInfo(
    version=_version(),
    built_at=os.getenv("BUILD_TIMESTAMP", datetime.now(timezone.utc).isoformat()),
    git_sha=_git_sha(),
)

__version__ = BUILD.version

