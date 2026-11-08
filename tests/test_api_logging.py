"""Тесты логирования обращений к API (INFO при успехе и при 429)."""

import json
import logging
from datetime import date

from wb_sync.app_config import AppConfig
from wb_sync.wb_api import WBClient


class FakeResponse:
    def __init__(self, status_code=200, content=b"[]", json_data=None, headers=None):
        self.status_code = status_code
        self.content = content if json_data is None else json.dumps(json_data).encode()
        self._json = json_data
        self.text = ""
        self.headers = headers or {}

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def make_client(tmp_path, responses):
    config = AppConfig(work_dir=tmp_path, api_token="tok", max_retries=3,
                       min_request_interval=0.0, retry_base_delay=0.0)
    client = WBClient(config)
    fake = FakeSession(responses)
    client._session = fake
    client._session.headers = {}
    return client, fake


def capture_logs(caplog):
    return [(r.levelname, r.getMessage()) for r in caplog.records]


def test_info_log_on_success(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wb_sync.wb_api")
    client, fake = make_client(
        tmp_path, [FakeResponse(json_data=[{"srid": "1"}])]
    )
    client.get_orders(date(2026, 10, 1), date(2026, 10, 1))
    msgs = capture_logs(caplog)
    assert any(lv == "INFO" and "→ 200" in m for lv, m in msgs), msgs


def test_info_log_on_429_and_retry(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wb_sync.wb_api")
    client, fake = make_client(
        tmp_path,
        [FakeResponse(status_code=429, content=b"{}", headers={"Retry-After": "0"}),
         FakeResponse(json_data=[{"srid": "1"}])],
    )
    client.get_orders(date(2026, 10, 1), date(2026, 10, 1))
    msgs = capture_logs(caplog)
    assert any("HTTP 429" in m for lv, m in msgs if lv == "INFO"), msgs
    assert any("→ 200" in m for lv, m in msgs if lv == "INFO"), msgs
    assert len(fake.calls) == 2  # 429 + успешный ретрай


def test_error_log_after_retries_exhausted(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="wb_sync.wb_api")
    resp = FakeResponse(status_code=429, content=b"{}", headers={"Retry-After": "0"})
    client, fake = make_client(tmp_path, [resp])
    import pytest
    try:
        client.get_orders(date(2026, 10, 1), date(2026, 10, 1))
        raised = False
    except Exception:
        raised = True
    assert raised
    msgs = capture_logs(caplog)
    # INFO-лог каждой неуспешной попытки
    assert sum(1 for lv, m in msgs if "HTTP 429" in m and "Попытка" in m) >= 4
    assert any(lv == "ERROR" and "окончательно" in m for lv, m in msgs), msgs
    assert len(fake.calls) == 4  # первая попытка + 3 ретрая (max_retries=3)
