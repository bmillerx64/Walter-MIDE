from types import ModuleType, SimpleNamespace

from mide.webull_runtime_inspection import (
    format_runtime_report,
    inspect_webull_runtime,
)


class MockDistribution:
    version = "9.8.7"
    files = [
        "webull_sdk/__init__.py",
        "webull_sdk/market.py",
        "webull_openapi_python_sdk-9.8.7.dist-info/METADATA",
        "unrelated.txt",
    ]

    def read_text(self, name):
        return "webull_sdk\n" if name == "top_level.txt" else None


def test_mocked_distribution_metadata_and_recursive_inspection():
    root = ModuleType("webull_sdk")
    root.__file__ = "/runtime/webull_sdk/__init__.py"
    root.__path__ = ["/runtime/webull_sdk"]

    class MarketClient:
        def quote_snapshot(self):
            return None

        def close(self):
            return None

    root.MarketClient = MarketClient
    child = ModuleType("webull_sdk.market")
    child.__file__ = "/runtime/webull_sdk/market.py"

    def history_bars():
        return []

    child.history_bars = history_bars
    modules = {"webull_sdk": root, "webull_sdk.market": child}

    report = inspect_webull_runtime(
        distribution_lookup=lambda name: MockDistribution(),
        module_importer=lambda name: modules[name],
        package_walker=lambda *args, **kwargs: [
            SimpleNamespace(name="webull_sdk.market")
        ],
    )

    assert report["installed"] is True
    assert report["version"] == "9.8.7"
    assert report["webull_files"] == [
        "webull_openapi_python_sdk-9.8.7.dist-info/METADATA",
        "webull_sdk/__init__.py",
        "webull_sdk/market.py",
    ]
    assert report["top_level_modules"] == [
        {"name": "webull_sdk", "importable": True, "error": None}
    ]
    sdk = next(module for module in report["modules"]
               if module["name"] == "webull_sdk")
    client = next(item for item in sdk["classes"] if item["name"] == "MarketClient")
    assert client["highlighted"] is True
    assert {item["name"] for item in client["methods"]} == {"close", "quote_snapshot"}
    assert "method: quote_snapshot [HIGHLIGHT]" in format_runtime_report(report)


def test_import_failure_is_exact_and_does_not_stop_remaining_modules():
    distribution = MockDistribution()
    distribution.read_text = lambda name: "webull_bad\nwebull_good\n"
    good = ModuleType("webull_good")
    good.__file__ = "/runtime/webull_good.py"

    def importer(name):
        if name == "webull_bad":
            raise RuntimeError("mock import exploded")
        return good

    report = inspect_webull_runtime(
        distribution_lookup=lambda name: distribution,
        module_importer=importer,
        package_walker=lambda *args, **kwargs: [],
    )

    assert report["top_level_modules"][0]["error"] == (
        "RuntimeError: mock import exploded"
    )
    assert [module["name"] for module in report["modules"]] == ["webull_good"]
    assert "Import webull_bad failed: RuntimeError: mock import exploded" in report["errors"]
