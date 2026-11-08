from datetime import date

import pytest

from wb_sync.app_config import AppConfig
from wb_sync.wb_api import WBClient, chunk_periods, CachedDataMissingError


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self.payload


class FakeSession:
    """Сессия-заглушка: считает вызовы, пагинацию v3 отдаёт по счётчику."""

    def __init__(self, orders_payload):
        self.headers = {}
        self.v1_calls = 0
        self.orders_payload = orders_payload

    def request(self, method, url, timeout=None, **kwargs):
        if "/api/v1/" in url:
            self.v1_calls += 1
            return FakeResponse([{"srid": f"s{self.v1_calls}"}], 200)
        if url.endswith("/api/v3/orders"):
            nxt = kwargs["json"].get("next", 0)
            if nxt == 0:
                return FakeResponse({"orders": self.orders_payload[:2], "next": 2}, 200)
            return FakeResponse({"orders": self.orders_payload[2:], "next": None}, 200)
        raise AssertionError(url)


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    return AppConfig(work_dir=tmp_path)


def test_chunk_periods():
    chunks = list(chunk_periods(date(2026, 10, 1), date(2026, 10, 31)))
    assert len(chunks) == 2
    assert chunks[0][0] == date(2026, 10, 1)
    assert chunks[1][1] == date(2026, 10, 31)


def test_get_orders_paginated_and_cached(cfg):
    client = WBClient(cfg)
    fake = FakeSession([])
    client.session = fake
    rows = client.get_orders(date(2026, 10, 1), date(2026, 10, 31))
    assert fake.v1_calls == 2  # два 30-дневных чанка
    assert len(rows) == 2
    # Кеш существует
    cached = client.load_orders(date(2026, 10, 1), date(2026, 10, 31))
    assert cached == rows


def test_cache_without_api(cfg):
    client = WBClient(cfg)
    client._save_cache("orders_2026-10-01_2026-10-30", date(2026, 10, 1), date(2026, 10, 30), [{"srid": "x"}])
    rows = client.load_orders(date(2026, 10, 1), date(2026, 10, 30))
    assert rows == [{"srid": "x"}]


def test_cache_missing_raises(cfg):
    client = WBClient(cfg)
    with pytest.raises(CachedDataMissingError):
        client.load_fbs_orders(date(2026, 10, 1), date(2026, 10, 30))


def test_v3_pagination(cfg):
    client = WBClient(cfg)
    client.session = FakeSession(
        [{"rid": f"r{i}", "nmId": 100 + i, "price": 2954800,
          "createdAt": 1761500000000, "statuses": {"isCancel": False, "supplierStatus": "sorted_to_ship"}}
         for i in range(4)]
    )
    rows = client.get_fbs_orders(date(2026, 10, 1), date(2026, 10, 31))
    assert len(rows) == 4  # 2 + 2 по пагинации через next
    assert client.normalize_fbs_status(rows[0]) == "Готов к отгрузке"


def test_normalize_cancel(cfg):
    client = WBClient(cfg)
    assert client.normalize_fbs_status({"statuses": {"isCancel": True}}) == "Отменен"
    assert client.normalize_fbs_status({"statuses": {"supplierStatus": "delivering"}}) == "Доставляется"


def test_rub_from_kopecks():
    assert WBClient.rub_from_kopecks(2954800) == 29548.0
