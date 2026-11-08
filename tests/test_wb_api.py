import json
from datetime import date
from unittest.mock import patch

import pytest

from wb_sync.app_config import AppConfig
from wb_sync.wb_api import (CachedDataMissingError, WBClient, chunk_periods,
                            normalize_v3_status)


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.content = json.dumps(payload).encode()

    def json(self):
        return self._payload

    def raise_for_status(self):
        assert self.status_code == 200, self.status_code


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, params=None, json=None, timeout=None):
        self.calls.append((method, url, params))
        if not self.responses:
            raise AssertionError("нет заготовленных ответов")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_cfg(tmp_path, **kw):
    import os
    os.environ.setdefault("API_TOKEN", "tok")
    return AppConfig(work_dir=tmp_path, **kw)


def test_chunk_periods():
    assert len(chunk_periods(date(2026, 10, 1), date(2026, 10, 31))) == 2
    assert chunk_periods(date(2026, 10, 1), date(2026, 10, 30)) == [(date(2026, 10, 1), date(2026, 10, 30))]
    with pytest.raises(ValueError):
        chunk_periods(date(2026, 10, 10), date(2026, 10, 1))


def test_normalize_cancel():
    assert normalize_v3_status("new") == "Ожидает сборки"
    assert normalize_v3_status("cancel") == "Отменен"
    assert normalize_v3_status("") == "неизвестно"


def test_sandbox_hosts(tmp_path):
    cfg = make_cfg(tmp_path, sandbox=True)
    client = WBClient(cfg)
    assert client._host(client.V1_HOST).startswith("https://statistics-api-sandbox.")
    assert client._host(client.CONTENT_HOST).startswith("https://content-api-sandbox.")


def test_get_orders_paginated_and_cached(tmp_path):
    cfg = make_cfg(tmp_path)
    client = WBClient(cfg)
    rows = [{"srid": f"s{i}", "date": "2026-10-05T00:00:00", "finishedPrice": 100000} for i in range(3)]
    with patch.object(client, "session", FakeSession([FakeResponse(rows)])):
        assert client.get_orders(date(2026, 10, 1), date(2026, 10, 30)) == rows
    # второй вызов — снова из сети (fetch_data=True), но кеш уже обновлён
    assert (tmp_path / "v1_orders_2026-10-01_2026-10-30.json").exists()


def test_cache_without_api(tmp_path):
    cfg = make_cfg(tmp_path, fetch_data=False)
    client = WBClient(cfg)
    (tmp_path / "v1_orders_2026-10-01_2026-10-30.json").write_text("[]")
    assert client.get_orders(date(2026, 10, 1), date(2026, 10, 30)) == []


def test_cache_missing_raises(tmp_path):
    cfg = make_cfg(tmp_path, fetch_data=False)
    client = WBClient(cfg)
    with pytest.raises(CachedDataMissingError):
        client.get_orders(date(2026, 10, 1), date(2026, 10, 30))


def test_v3_pagination(tmp_path):
    cfg = make_cfg(tmp_path)
    client = WBClient(cfg)
    session = FakeSession([
        FakeResponse({"orders": [{"rid": "r1"}], "next": 500}),
        FakeResponse({"orders": [{"rid": "r2"}], "next": 0}),
    ])
    with patch.object(client, "session", session):
        rows = client.get_v3_orders(date(2026, 10, 1), date(2026, 10, 30))
    assert [r["rid"] for r in rows] == ["r1", "r2"]
    assert len(session.calls) == 2
    assert session.calls[0][2]["next"] == 0
    assert session.calls[1][2]["next"] == 500


def test_retry_on_429_with_delay(tmp_path):
    cfg = make_cfg(tmp_path, max_retries=1, retry_base_delay=0.0, min_request_interval=0.0)
    client = WBClient(cfg)
    session = FakeSession([
        FakeResponse({}, status_code=429, headers={"Retry-After": "0"}),
        FakeResponse([{"ok": 1}]),
    ])
    with patch.object(client, "session", session):
        assert client._fetch_v1("/api/v1/supplier/orders", "orders", date(2026, 10, 1), date(2026, 10, 30)) == [{"ok": 1}]
    assert len(session.calls) == 2


def test_429_logged(caplog, tmp_path):
    cfg = make_cfg(tmp_path, max_retries=0, min_request_interval=0.0)
    client = WBClient(cfg)
    import requests as _r
    with patch.object(client, "session", FakeSession([FakeResponse({}, status_code=429)])), \
            caplog.at_level("INFO"):
        with pytest.raises((RuntimeError, _r.HTTPError)):
            client.get_stocks()
    assert any("HTTP 429" in r.message or "429" in str(r.msg) for r in caplog.records)


def test_ping_logging_info(caplog, tmp_path):
    cfg = make_cfg(tmp_path, min_request_interval=0.0)
    client = WBClient(cfg)
    with patch.object(client, "session", FakeSession([FakeResponse({"errMsg": None})])), \
            caplog.at_level("INFO"):
        client.ping()
    assert any("Попытка" in r.message for r in caplog.records)
