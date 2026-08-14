import mide.webull_connection
from mide.webull_live import LiveWebullProvider


def test_live_assets_method_is_native_cutover():
    assert getattr(LiveWebullProvider.assets, "_walter_webull_native_discovery", False) is True
