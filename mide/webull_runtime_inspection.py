"""Temporary, read-only inspection of the Webull SDK installed at runtime."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import pkgutil
from typing import Any, Callable


DISTRIBUTION_NAME = "webull-openapi-python-sdk"
HIGHLIGHT_TERMS = (
    "client", "api", "auth", "market", "quote", "snapshot", "history",
    "bar", "stream", "websocket", "mqtt",
)


def _highlighted(name: str) -> bool:
    lowered = name.lower()
    return any(term in lowered for term in HIGHLIGHT_TERMS)


def _top_level_names(distribution: Any, files: list[str]) -> list[str]:
    """Return import candidates declared by, or safely inferred from, a wheel."""
    declared = distribution.read_text("top_level.txt")
    if declared:
        return sorted({line.strip() for line in declared.splitlines()
                       if line.strip() and line.strip().isidentifier()})

    names: set[str] = set()
    for file_name in files:
        parts = file_name.replace("\\", "/").split("/")
        first = parts[0]
        if first.endswith(".py"):
            candidate = first[:-3]
        elif len(parts) > 1 and not first.endswith((".dist-info", ".data")):
            candidate = first
        else:
            continue
        if candidate.isidentifier():
            names.add(candidate)
    return sorted(names)


def _module_details(module_name: str, module: Any) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for name, value in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        if inspect.isclass(value):
            methods = sorted(
                method_name for method_name, method in inspect.getmembers(value)
                if not method_name.startswith("_") and callable(method)
            )
            classes.append({
                "name": name,
                "highlighted": _highlighted(name),
                "methods": [
                    {"name": method, "highlighted": _highlighted(method)}
                    for method in methods
                ],
            })
        elif inspect.isfunction(value) or inspect.isbuiltin(value):
            functions.append({"name": name, "highlighted": _highlighted(name)})
    return {
        "name": module_name,
        "file": str(getattr(module, "__file__", None) or "<no file>"),
        "classes": classes,
        "functions": functions,
    }


def inspect_webull_runtime(
    *,
    distribution_lookup: Callable[[str], Any] = importlib.metadata.distribution,
    module_importer: Callable[[str], Any] = importlib.import_module,
    package_walker: Callable[..., Any] = pkgutil.walk_packages,
) -> dict[str, Any]:
    """Inspect installed metadata and modules without reading credentials."""
    report: dict[str, Any] = {
        "distribution": DISTRIBUTION_NAME,
        "installed": False,
        "version": None,
        "webull_files": [],
        "top_level_modules": [],
        "modules": [],
        "errors": [],
    }
    try:
        distribution = distribution_lookup(DISTRIBUTION_NAME)
    except Exception as exc:
        report["errors"].append(
            f"Distribution lookup failed: {type(exc).__name__}: {exc}"
        )
        return report

    report["installed"] = True
    report["version"] = str(distribution.version)
    files = [str(path) for path in (distribution.files or [])]
    report["webull_files"] = sorted(
        path for path in files if "webull" in path.lower()
    )
    top_levels = _top_level_names(distribution, files)
    discovered: set[str] = set(top_levels)
    imported: dict[str, Any] = {}

    for name in top_levels:
        row = {"name": name, "importable": False, "error": None}
        try:
            imported[name] = module_importer(name)
            row["importable"] = True
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
            report["errors"].append(f"Import {name} failed: {row['error']}")
        report["top_level_modules"].append(row)

    for name, module in tuple(imported.items()):
        package_path = getattr(module, "__path__", None)
        if package_path is None:
            continue
        walk_errors: list[str] = []

        def onerror(failed_name: str) -> None:
            walk_errors.append(f"Package walk {failed_name} failed")

        try:
            for module_info in package_walker(
                package_path, prefix=f"{name}.", onerror=onerror
            ):
                discovered.add(module_info.name)
        except Exception as exc:
            report["errors"].append(
                f"Package walk {name} failed: {type(exc).__name__}: {exc}"
            )
        report["errors"].extend(walk_errors)

    for name in sorted(discovered):
        module = imported.get(name)
        if module is None:
            try:
                module = module_importer(name)
            except Exception as exc:
                report["errors"].append(
                    f"Import {name} failed: {type(exc).__name__}: {exc}"
                )
                continue
        try:
            report["modules"].append(_module_details(name, module))
        except Exception as exc:
            report["errors"].append(
                f"Inspect {name} failed: {type(exc).__name__}: {exc}"
            )
    return report


def format_runtime_report(report: dict[str, Any]) -> str:
    """Create the credential-free plain-text download artifact."""
    lines = [
        "WEBULL SDK RUNTIME INSPECTION",
        f"Distribution: {report['distribution']}",
        f"Installed: {report['installed']}",
        f"Version: {report['version'] or 'N/A'}",
        "", "DISTRIBUTION FILES CONTAINING WEBULL",
    ]
    lines.extend(report["webull_files"] or ["(none)"])
    lines.extend(["", "TOP-LEVEL MODULES"])
    for module in report["top_level_modules"]:
        status = "importable" if module["importable"] else f"FAILED: {module['error']}"
        lines.append(f"- {module['name']}: {status}")
    lines.extend(["", "DISCOVERED MODULE INSPECTION"])
    for module in report["modules"]:
        lines.extend([f"MODULE {module['name']}", f"  file: {module['file']}"])
        for class_info in module["classes"]:
            marker = " [HIGHLIGHT]" if class_info["highlighted"] else ""
            lines.append(f"  class: {class_info['name']}{marker}")
            for method in class_info["methods"]:
                marker = " [HIGHLIGHT]" if method["highlighted"] else ""
                lines.append(f"    method: {method['name']}{marker}")
        for function in module["functions"]:
            marker = " [HIGHLIGHT]" if function["highlighted"] else ""
            lines.append(f"  function: {function['name']}{marker}")
    lines.extend(["", "ERRORS"])
    lines.extend(report["errors"] or ["(none)"])
    return "\n".join(lines) + "\n"
