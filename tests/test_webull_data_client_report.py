from types import ModuleType

from mide.webull_data_client_report import build_report


class GetSnapshotRequest:
    pass


class Parent:
    def inherited(self, request: GetSnapshotRequest, limit: int = 1):
        """Fetch a quote snapshot."""


class DataClient(Parent):
    """Mock data client."""

    def __init__(self, api_key: str, *, timeout: float = 2.0):
        pass

    def history(self, request: GetSnapshotRequest | None = None):
        """Return historical bars."""

    def _private(self):
        pass


class DataStreamingClient:
    def subscribe(self, symbols: list[str]) -> None:
        """Create subscriptions for instruments."""


def test_report_uses_runtime_signatures_docs_bases_and_annotations():
    modules = {}
    for module_name, cls in (
        ("webull.data.data_client", DataClient),
        ("webull.data.data_streaming_client", DataStreamingClient),
    ):
        module = ModuleType(module_name)
        setattr(module, cls.__name__, cls)
        modules[module_name] = module

    report = build_report(importer=modules.__getitem__)

    client = report["classes"][0]
    assert client["constructor_signature"] == (
        "(api_key: str, *, timeout: float = 2.0)"
    )
    assert client["docstring"] == "Mock data client."
    assert client["base_classes"] == [f"{__name__}.Parent"]
    assert [method["name"] for method in client["public_methods"]] == [
        "history", "inherited"
    ]
    inherited = client["public_methods"][1]
    assert inherited["signature"].endswith("limit: int = 1)")
    assert inherited["docstring"] == "Fetch a quote snapshot."
    assert inherited["defined_by"] == f"{__name__}.Parent"
    assert inherited["get_requests"] == [f"{__name__}.GetSnapshotRequest"]
    assert inherited["categories"]["snapshot"] is True
    assert inherited["categories"]["quotes"] is True

    streaming = report["classes"][1]["public_methods"][0]
    assert streaming["categories"]["subscriptions"] is True
    assert streaming["categories"]["instruments"] is True
