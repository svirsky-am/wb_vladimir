import json
from datetime import date

import pytest

from wb_sync import wb_api
from wb_sync.app_config import AppConfig


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)
        self.url = "https://test"

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        return self.responses.pop(0)

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return self.responses.pop(0)


def make_config(tmp_path, **kw):
    return AppConfig(work_dir=str(tmp_path), api_token="tok", **kw)


def test_chunk_periods():
    chunks = wb_api.chunk_periods(date(2026, 10, 1), date(2026, 11, 30))
    assert len(chunks) == 3
    assert chunks[0] == (date(2026, 10, 1), date(2026, 10, 30))
    assert chunks[1] == (date(2026, 10, 31), date(2026, 11, 29))
    assert chunks[2] == (date(2026, 11, 30), date(2026, 11, 30))
    # период в 30 дней (dateFrom/dateTo включительно) -> один кусок
    assert wb_api.chunk_periods(date(2026, 10, 1), date(2026, 10, 30)) == [
        (date(2026, 10, 1), date(2026, 10, 30))
    ]


def test_get_orders_paginated_and_cached(tmp_path):
    cfg = make_config(tmp_path)
    session = FakeSession([FakeResponse([{"srid": "1", "finishedPrice": 10000}])])
    client = wb_api.WBClient(cfg, session=session)
    rows = client.get_orders(date(2026, 10, 1), date(2026, 10, 30))
    assert len(rows) == 1
    assert any(p.name.startswith("wb_orders_2026-10-01_2026-10-30") for p in tmp_path.iterdir())
    # fetch_data=False -> читаем из кеша, сеть не трогаем
    cfg2 = make_config(tmp_path)
    cfg2.fetch_data = False
    client2 = wb_api.WBClient(cfg2, session=FakeSession([]))
    assert client2.get_orders(date(2026, 10, 1), date(2026, 10, 30)) == rows


def test_cache_missing_raises(tmp_path):
    cfg = make_config(tmp_path)
    cfg.fetch_data = False
    client = wb_api.WBClient(cfg, session=FakeSession([]))
    with pytest.raises(wb_api.CachedDataMissingError):
        client.get_orders(date(2026, 10, 1), date(2026, 10, 30))


def test_retry_on_429(tmp_path):
    cfg = make_config(tmp_path)
    session = FakeSession([FakeResponse({}, status_code=429), FakeResponse([])])
    client = wb_api.WBClient(cfg, session=session)
    rows = client.get_orders(date(2026, 10, 1), date(2026, 10, 30))
    assert rows == []
    assert len(session.calls) == 2


def test_v3_pagination(tmp_path):
    cfg = make_config(tmp_path)
    page1 = {"orders": [{"rid": "r1", "nmId": 1, "price": 100, "createdAt": 1792195200000,
                          "statuses": {"isCancel": False, "supplierStatus": "delivering"}}],
             "next": 1}
    page2 = {"orders": [{"rid": "r2", "nmId": 2, "price": 200, "createdAt": 1792195200000,
                          "statuses": {"isCancel": True, "supplierStatus": "sold"}}]}
    session = FakeSession([FakeResponse(page1), FakeResponse(page2)])
    client = wb_api.WBClient(cfg, session=session)
    rows = client.get_fbs_orders(date(2026, 10, 1), date(2026, 10, 31))
    assert [r["rid"] for r in rows] == ["r1", "r2"]
    # второй вызов был с next=1, дальше — стоп (next отсутствует)
    assert len(session.calls) == 2
    assert session.calls[0][2]["next"] == 0
    assert session.calls[1][2]["next"] == 1


def test_normalize_cancel(tmp_path):
    cfg = make_config(tmp_path)
    client = wb_api.WBClient(cfg, session=FakeSession([]))
    assert client.normalize_status({"statuses": {"isCancel": True}}) == "Отменен"
    assert client.normalize_status({"statuses": {"isCancel": False, "supplierStatus": "delivering"}}) == "Доставляется"
    assert client.normalize_status({"statuses": {"isCancel": False, "supplierStatus": "awaiting_deliver"}}) == "Готов к отгрузке"


def test_rub_from_kopecks(tmp_path):
    cfg = make_config(tmp_path)
    session = FakeSession([FakeResponse([{"srid": "1", "finishedPrice": 2954800}])])
    client = wb_api.WBClient(cfg, session=session)
    assert client.get_orders(date(2026, 10, 1), date(2026, 10, 30))[0]["finishedPrice"] == 2954800
