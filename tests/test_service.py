import asyncio

from wb_sync.service import ping_wb, sync_cycle


class FakeClient:
    config = type("C", (), {"fetch_interval_minutes": 1, "fetch_data": True})()

    def __init__(self):
        self.pinged = 0
        self.synced = 0

    def ping(self):
        self.pinged += 1
        if self.pinged < 2:
            raise RuntimeError("down")

    def sync(self):
        self.synced += 1
        return {"orders": 1}


def test_ping_retries_then_ok():
    client = FakeClient()
    ok = asyncio.run(ping_wb(client, attempts=3))
    assert ok and client.pinged == 2


def test_ping_fails_all():
    class Bad(FakeClient):
        def ping(self):
            self.pinged += 1
            raise RuntimeError("down")
    assert asyncio.run(ping_wb(Bad(), attempts=2)) is False


def test_sync_cycle_fills_db(tmp_path, monkeypatch):
    import wb_sync.core as core
    import wb_sync.service as service
    calls = []

    def fake_sync(cfg, client):
        calls.append(1)
        return {"orders": 0}

    monkeypatch.setattr(service, "sync_data", fake_sync)
    counts = asyncio.run(service.sync_cycle(FakeClient()))
    assert counts == {"orders": 0} and len(calls) == 1


def test_service_survives_errors(tmp_path, monkeypatch):
    import wb_sync.service as service

    class FlakyClient(FakeClient):
        pass

    flaky = FlakyClient()
    state = {"n": 0}

    async def fake_sync_cycle(client):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("boom")

    async def fake_wait_for(*a, **kw):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(service, "ping_wb", lambda *a, **kw: _true())
    monkeypatch.setattr(service, "sync_cycle", fake_sync_cycle)
    import asyncio as _a
    orig_wait = _a.wait_for
    _a_wait = fake_wait_for

    async def run():
        await service.run_service(type("C", (), {"fetch_interval_minutes": 0.0001, "fetch_data": True})(), cycles=2)

    monkeypatch.setattr(service.asyncio, "wait_for", fake_wait_for)
    asyncio.run(run())
    assert state["n"] == 2


def _true():
    return True
