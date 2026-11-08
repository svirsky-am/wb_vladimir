"""asyncio-служба: периодический фетч WB -> SQLite. Интервал берётся из AppConfig."""
from __future__ import annotations

import asyncio
import signal

from .app_config import AppConfig
from .core import sync_cards, sync_data
from .db import get_engine
from .logging_setup import setup_logging
from .wb_api import WBClient


async def sync_cycle(config, engine, client) -> dict:
    """Один цикл: выгрузка данных + карточек (в отдельном потоке, чтобы не блокировать loop)."""
    stats = await asyncio.to_thread(sync_data, config, engine, client)
    stats.update(await asyncio.to_thread(sync_cards, config, engine, client))
    return stats


async def run_service(config, cycles: int | None = None):
    """Бесконечный цикл sync -> sleep(fetch_interval_minutes). cycles — для тестов.

    Graceful shutdown по SIGINT/SIGTERM.
    """
    engine = get_engine(config)
    client = WBClient(config)
    stop = asyncio.Event()

    def handle_signal():
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except NotImplementedError:
            pass  # Windows: отрабатывает KeyboardInterrupt

    done = 0
    try:
        while not stop.is_set() and (cycles is None or done < cycles):
            try:
                stats = await sync_cycle(config, engine, client)
                print(f"[service] цикл {done + 1}: {stats}")
            except Exception as exc:  # noqa: BLE001 — служба переживает ошибку цикла
                print(f"[service] ошибка цикла: {exc}")
            done += 1
            if cycles is None or done < cycles:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=config.fetch_interval_minutes * 60)
                except asyncio.TimeoutError:
                    pass
    finally:
        engine.dispose()
    return done
