from mide.webull_native_radar import _rows


class OfficialResponseShape:
    status_code = 200
    def json(self):
        return {"data": [{"symbol": "TEST", "price": "1.00"}]}


def test_rows_decodes_official_sdk_response_json_method():
    assert _rows(OfficialResponseShape()) == [{"symbol": "TEST", "price": "1.00"}]
