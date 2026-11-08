"""Asyncio-служба: периодический fetch по конфигу + graceful shutdown."""

import asyncio
import logging
import signal

from .app_config import AppConfig
from .core import sync_data

logger = logging.getLogger("wb_sync.service")


async def sync_cycle(app_config: AppConfig, client=None) -> dict:
    return await asyncio.to_thread(sync_data, app_config, client)


async def run_service(app_config: AppConfig, client=None, stop_event: asyncio.Event | None = None):
    """Цикл: sync -> sleep(fetch_interval_minutes). Ошибка цикла не роняет службу."""
    stop_event = stop_event or asyncio.Event()
    interval = app_config.fetch_interval_minutes * 60

    def _handle_signal(sig_name: str):
        logger.info("Получен сигнал %s, останавливаемся", sig_name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig.name)
        except NotImplementedError:
            pass  # Windows

    logger.info("Служба запущена, интервал %d мин, fetch_data=%s",
                app_config.fetch_interval_minutes, app_config.fetch_data)
    while not stop_event.is_set():
        try:
            stats = await sync_cycle(app_config, client)
            logger.info("Цикл фетча: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка в цикле фетча, продолжаем по расписанию")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
    logger.info("Служба остановлена")


def serve(app_config: AppConfig, client=None):
    asyncio.run(run_service(app_config, client))
