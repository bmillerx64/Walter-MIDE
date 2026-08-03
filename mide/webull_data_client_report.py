"""Export a narrow, read-only inventory of the Webull data client classes."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import re
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints


TARGETS = (
    ("webull.data.data_client", "DataClient"),
    ("webull.data.data_streaming_client", "DataStreamingClient"),
)

CATEGORY_TERMS = {
    "snapshot": ("snapshot",),
    "quotes": ("quote", "quotes"),
    "historical bars": ("bar", "bars", "history", "historical", "kline"),
    "instruments": ("instrument", "instruments", "ticker", "tickers"),
    "screener": ("screener", "screeners", "ranking", "rankings"),
    "subscriptions": ("subscribe", "subscription", "unsubscribe"),
}


def _qualified_name(value: Any) -> str:
    return f"{value.__module__}.{value.__qualname__}"


def _signature(value: Any) -> str:
    """Return the SDK's signature without constructing a client."""
    return str(inspect.signature(value))


def _annotation_classes(annotation: Any) -> set[type]:
    if annotation is inspect.Parameter.empty:
        return set()
    if inspect.isclass(annotation):
        return {annotation}
    classes: set[type] = set()
    for argument in get_args(annotation) if get_origin(annotation) else ():
        classes.update(_annotation_classes(argument))
    return classes


def _get_requests(method: Any) -> list[str]:
    requests: set[str] = set()
    signature = inspect.signature(method)
    try:
        resolved = get_type_hints(method)
    except (NameError, TypeError):
        resolved = {}
    for parameter in signature.parameters.values():
        annotation = resolved.get(parameter.name, parameter.annotation)
        for annotation in _annotation_classes(annotation):
            if re.fullmatch(r"Get.*Request", annotation.__name__):
                requests.add(_qualified_name(annotation))
        if isinstance(annotation, str):
            requests.update(re.findall(r"\bGet[A-Za-z0-9_]*Request\b", annotation))
    return sorted(requests)


def _categories(name: str, method: Any, requests: list[str]) -> dict[str, bool]:
    """Classify only from SDK-published identifiers and documentation.

    This deliberately avoids interpreting implementation behavior. A false value
    means the inspected metadata contains no evidence for that category.
    """
    evidence = " ".join((name, inspect.getdoc(method) or "", *requests))
    evidence = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", evidence).casefold()
    words = set(re.findall(r"[a-z]+", evidence))
    return {
        category: any(term in words for term in terms)
        for category, terms in CATEGORY_TERMS.items()
    }


def inspect_class(cls: type) -> dict[str, Any]:
    methods = []
    for name, method in inspect.getmembers(cls, predicate=callable):
        if name.startswith("_"):
            continue
        requests = _get_requests(method)
        owner = next(base for base in cls.__mro__ if name in base.__dict__)
        methods.append({
            "name": name,
            "signature": _signature(method),
            "docstring": inspect.getdoc(method),
            "defined_by": _qualified_name(owner),
            "categories": _categories(name, method, requests),
            "get_requests": requests,
        })
    return {
        "class": _qualified_name(cls),
        "constructor_signature": _signature(cls),
        "docstring": inspect.getdoc(cls),
        "base_classes": [_qualified_name(base) for base in cls.__bases__],
        "public_methods": methods,
    }


def build_report(importer=importlib.import_module) -> dict[str, Any]:
    classes = []
    for module_name, class_name in TARGETS:
        module = importer(module_name)
        classes.append(inspect_class(getattr(module, class_name)))
    return {
        "scope": [f"{module}.{name}" for module, name in TARGETS],
        "classification_basis": (
            "Exact whole-word matches in SDK method names, docstrings, and "
            "Get*Request annotation names; false means not evidenced by that metadata."
        ),
        "classes": classes,
    }


def export_report(destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_report(), indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="destination JSON report")
    args = parser.parse_args(argv)
    print(export_report(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
