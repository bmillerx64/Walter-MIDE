"""Helpers for exposing Walter's existing runtime history files."""

from pathlib import Path


def read_runtime_history(path: str | Path) -> bytes | None:
    """Return a runtime history file unchanged, or ``None`` when it is absent."""
    history_path = Path(path)
    if not history_path.is_file():
        return None
    return history_path.read_bytes()
