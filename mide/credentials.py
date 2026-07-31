"""Credential resolution shared by Streamlit and command-line integrations."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


WEBULL_CREDENTIAL_NAMES = (
    "WEBULL_APP_KEY",
    "WEBULL_APP_SECRET",
)


@dataclass(frozen=True)
class Credential:
    """A resolved credential and its non-sensitive provenance."""

    value: str
    source: str

    @property
    def present(self) -> bool:
        return bool(self.value)


def _development_dotenv(path: Path) -> dict[str, str]:
    """Read a simple local .env only when development is explicitly selected."""
    if os.getenv("WALTER_ENV", "").strip().lower() not in {"dev", "development", "local"}:
        return {}
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def load_credentials(
    names: tuple[str, ...],
    *,
    secrets: Mapping[str, object] | None = None,
    dotenv_path: str | Path = ".env",
) -> dict[str, Credential]:
    """Resolve names in Secrets > environment > development .env order."""
    secret_values = secrets or {}
    dotenv_values = _development_dotenv(Path(dotenv_path))
    resolved: dict[str, Credential] = {}
    for name in names:
        secret = str(secret_values.get(name, "") or "").strip()
        environment = os.getenv(name, "").strip()
        local = dotenv_values.get(name, "").strip()
        if secret:
            resolved[name] = Credential(secret, "Streamlit Secrets")
        elif environment:
            resolved[name] = Credential(environment, "environment")
        elif local:
            resolved[name] = Credential(local, "local .env")
        else:
            resolved[name] = Credential("", "not configured")
    return resolved


def credential_diagnostics(credentials: Mapping[str, Credential]) -> tuple[str, ...]:
    """Return safe startup messages; credential values are never included."""
    return tuple(
        f"{name}: {'present' if credential.present else 'missing'} ({credential.source})"
        for name, credential in credentials.items()
    )
