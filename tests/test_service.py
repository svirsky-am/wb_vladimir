import asyncio

import pytest

from wb_sync.app_config import AppConfig
from wb_sync.service import sync_cycle, run_service


class FakeClient:
    def get_orders(self, f, t):
        return [{"srid": "s1", "date": "2026-10-05", "supplierArticle": "A",
                 "finishedPrice": 100.0, "isCancel": False}]

    def get_sales(self, f, t):
        return []

    def get_fbs_orders(self, f, t):
        return []


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    return AppConfig(work_dir=tmp_path)


async def test_sync_cycle_fills_db(cfg, monkeypatch):
    monkeypatch.setattr("wb_sync.core.WBClient", lambda c: FakeClient())
    stats = await sync_cycle(cfg)
    assert stats["orders"] == 1
    assert stats["new_orders"] == 1


async def test_run_service_stops_after_cycles(cfg, monkeypatch):
    calls = []

    async def fake_cycle(c, client=None):
        calls.append(1)
        return {}

    monkeypatch.setattr("wb_sync.service.sync_cycle", fake_cycle)
    stop = asyncio.Event()
    # интервал маленький, чтобы тест не висел
    cfg.fetch_interval_minutes = 0.0005

    async def stopper():
        await asyncio.sleep(0.05)
        stop.set()

    asyncio.create_task(stopper())
    await run_service(cfg, stop_event=stop)
    assert len(calls) >= 1


async def test_service_survives_errors(cfg, monkeypatch):
    async def broken_cycle(c, client=None):
        raise RuntimeError("WB недоступен")

    monkeypatch.setattr("wb_sync.service.sync_cycle", broken_cycle)
    stop = asyncio.Event()
    cfg.fetch_interval_minutes = 0.0005

    async def stopper():
        await asyncio.sleep(0.05)
        stop.set()

    asyncio.create_task(stopper())
    await run_service(cfg, stop_event=stop)  # не должно упасть
