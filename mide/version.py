"""The single authoritative source of Walter build identity.

GS387 adds live checkout-vs-runtime freshness truth. Streamlit Community Cloud can
advance the repository checkout without replacing an already-imported Python
module graph immediately. In that state the old ``BUILD`` object used to keep
showing a plausible SHA even though newer files were present on disk. Walter now
compares the SHA captured when this module loaded with the checkout's current
``HEAD`` every time the displayed SHA is requested.

This is deployment/runtime observability only. It does not reload modules, restart
the process, schedule scans, or affect any market/trading decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

# Import after the core modules have loaded but before app.py binds the live
# behavioral decision function. This activates the narrow live-market safety
# overlays for share-structure conflicts and thin-participation promotions.
from . import live_safety as _live_safety  # noqa: F401


REPO_ROOT = Path(__file__).parents[1]
UNKNOWN_SHA = "unknown"


def _version() -> str:
    return (REPO_ROOT / "VERSION").read_text().strip()


def _checkout_git_sha() -> str:
    """Read the repository checkout currently present on disk, ignoring env vars."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN_SHA


def _git_sha() -> str:
    """Capture the SHA identity of this Python runtime at module import time."""
    configured = os.getenv("GIT_COMMIT_SHA") or os.getenv("RENDER_GIT_COMMIT")
    if configured:
        return configured[:12]
    return _checkout_git_sha()


def _known_sha(value: str | None) -> bool:
    text = str(value or "").strip()
    return bool(text and text.lower() != UNKNOWN_SHA)


@dataclass(frozen=True)
class BuildInfo:
    version: str
    built_at: str
    loaded_git_sha: str

    @property
    def checkout_git_sha(self) -> str:
        """Current checkout HEAD, evaluated dynamically rather than at import time."""
        return _checkout_git_sha()

    @property
    def runtime_stale(self) -> bool:
        """True only when both SHA identities are known and demonstrably differ."""
        checkout = self.checkout_git_sha
        return (
            _known_sha(self.loaded_git_sha)
            and _known_sha(checkout)
            and checkout != self.loaded_git_sha
        )

    @property
    def git_sha(self) -> str:
        """Operator-facing runtime SHA, visibly warning when the checkout advanced."""
        loaded = str(self.loaded_git_sha or UNKNOWN_SHA)
        checkout = self.checkout_git_sha
        if (
            _known_sha(loaded)
            and _known_sha(checkout)
            and checkout != loaded
        ):
            return f"{loaded} ⚠ RESTART→{checkout}"
        return loaded

    def freshness(self) -> dict[str, object]:
        """Structured diagnostic truth for tests and future operator surfaces."""
        checkout = self.checkout_git_sha
        stale = (
            _known_sha(self.loaded_git_sha)
            and _known_sha(checkout)
            and checkout != self.loaded_git_sha
        )
        return {
            "loaded_git_sha": self.loaded_git_sha,
            "checkout_git_sha": checkout,
            "runtime_stale": stale,
            "status": "STALE_RUNTIME" if stale else "CURRENT",
        }


BUILD = BuildInfo(
    version=_version(),
    built_at=os.getenv("BUILD_TIMESTAMP", datetime.now(timezone.utc).isoformat()),
    loaded_git_sha=_git_sha(),
)

__version__ = BUILD.version
