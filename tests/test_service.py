"""Тесты службы требуют pytest-asyncio (asyncio_mode = auto в pyproject)."""
from datetime import date

import pytest
import pytest_asyncio  # noqa: F401

from wb_sync import db, service
from wb_sync.app_config import AppConfig
from wb_sync.wb_api import WBClient


class StubClient:
    def __init__(self):
        self.calls = 0

    def get_orders(self, start, end):
        self.calls += 1
        return [{"srid": f"o{self.calls}", "date": "2026-10-05T00:00:00",
                 "supplierArticle": "A", "subjectName": "S", "warehouseName": "W",
                 "totalPrice": 10000, "discountPercent": 0, "finishedPrice": 9500, "isCancel": False}]

    def get_sales(self, start, end):
        return []

    def get_fbs_orders(self, start, end):
        return []

    def get_stocks(self):
        return []

    def get_incomes(self):
        return []

    def get_cards(self):
        return []


@pytest.fixture()
def config(tmp_path):
    return AppConfig(work_dir=str(tmp_path / "wd"), api_token="tok",
                     fetch_interval_minutes=1, database_path="wb_sync.db")


async def test_sync_cycle_fills_db(config):
    engine = db.get_engine(config)
    client = StubClient()
    stats = await service.sync_cycle(config, engine, client)
    assert stats["orders"] == 1 and stats["cards"] == 0
    assert len(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))) == 1
    engine.dispose()


async def test_run_service_stops_after_cycles(config, monkeypatch):
    monkeypatch.setattr(service, "get_engine", lambda cfg: db.get_engine(cfg))
    monkeypatch.setattr(service, "WBClient", lambda cfg: StubClient())
    # подменяем sleep, чтобы не ждать реальный интервал
    import asyncio as _aio
    real_sleep = _aio.sleep

    async def fast_sleep(sec):
        await real_sleep(0)

    monkeypatch.setattr(_aio, "sleep", fast_sleep)
    done = await service.run_service(config, cycles=3)
    assert done == 3


async def test_service_survives_errors(config, monkeypatch):
    class BrokenClient(StubClient):
        def get_orders(self, start, end):
            raise RuntimeError("network down")

    monkeypatch.setattr(service, "get_engine", lambda cfg: db.get_engine(cfg))
    monkeypatch.setattr(service, "WBClient", lambda cfg: BrokenClient())
    import asyncio as _aio
    real_sleep = _aio.sleep

    async def fast_sleep(sec):
        await real_sleep(0)

    monkeypatch.setattr(_aio, "sleep", fast_sleep)
    done = await service.run_service(config, cycles=2)
    assert done == 2
