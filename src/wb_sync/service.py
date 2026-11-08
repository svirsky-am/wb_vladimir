"""asyncio-служба: периодический фетч данных по конфигу."""

import asyncio
import logging
import signal
import sys
from datetime import date, timedelta

from wb_sync.app_config import AppConfig
from wb_sync import db
from wb_sync.logging_setup import setup_logging
from wb_sync.wb_api import WBClient
from wb_sync.core import sync_data

logger = logging.getLogger("wb_sync.service")


def sync_cycle(config, engine, client):
    d_to = date.today()
    d_from = d_to - timedelta(days=config.fetch_window_days - 1)
    return sync_data(config, engine, client, d_from, d_to)


async def run_service(config, engine, client, max_cycles=None):
    """Цикл: sync -> sleep(fetch_interval_minutes). Ошибка цикла не роняет службу."""
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # Windows / не-основной поток

    logger.info("Служба запущена: интервал %.0f мин, fetch_data=%s",
                config.fetch_interval_minutes, config.fetch_data)
    cycles = 0
    while not stop.is_set():
        cycles += 1
        logger.info("Цикл %d: начало", cycles)
        try:
            result = await asyncio.to_thread(sync_cycle, config, engine, client)
            logger.info("Цикл %d: готово %s", cycles, result)
        except Exception:
            logger.exception("Цикл %d: ошибка синхронизации", cycles)
        if max_cycles is not None and cycles >= max_cycles:
            logger.info("Достигнут лимит циклов (%d), остановка", max_cycles)
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=config.fetch_interval_minutes * 60)
        except asyncio.TimeoutError:
            pass
    logger.info("Служба остановлена")


def main():
    config = AppConfig()
    setup_logging(config)
    engine = db.make_engine(config)
    db.init_db(engine)
    client = WBClient(config)
    asyncio.run(run_service(config, engine, client))


if __name__ == "__main__":
    main()
