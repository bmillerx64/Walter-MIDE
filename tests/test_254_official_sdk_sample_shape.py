from mide.webull_native_radar import _plain


class Response:
    status_code = 200
    def json(self): return {"data": [{"symbol": "XYZ"}]}


def test_plain_decodes_response_json_payload():
    assert _plain(Response()) == {"data": [{"symbol": "XYZ"}]}
