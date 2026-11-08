"""asyncio-служба: ping до старта, затем цикл sync -> пауза."""
import asyncio
import logging
import signal

from .core import sync_data
from .wb_api import WBClient

logger = logging.getLogger(__name__)


async def ping_wb(client: WBClient, attempts: int = 3) -> bool:
    for i in range(1, attempts + 1):
        try:
            await asyncio.to_thread(client.ping)
            logger.info("Ping WB: OK (попытка %d/%d)", i, attempts)
            return True
        except Exception:
            logger.warning("Ping WB не удался (попытка %d/%d)", i, attempts, exc_info=True)
            await asyncio.sleep(2)
    return False


async def sync_cycle(client: WBClient) -> dict:
    return await asyncio.to_thread(sync_data, client.config, client)


async def run_service(config, cycles: int | None = None) -> None:
    client = WBClient(config)
    if not await ping_wb(client):
        logger.critical("WB недоступен после ping — служба не запускается")
        raise SystemExit(1)
    logger.info("Служба запущена: интервал %d мин, fetch_data=%s",
                config.fetch_interval_minutes, config.fetch_data)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    done = 0
    while not stop.is_set():
        try:
            counts = await sync_cycle(client)
            logger.info("Цикл %d завершён: %s", done + 1, counts)
        except Exception:
            logger.exception("Ошибка цикла — служба продолжает работу")
        done += 1
        if cycles is not None and done >= cycles:
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=config.fetch_interval_minutes * 60)
        except asyncio.TimeoutError:
            pass
    logger.info("Служба остановлена (циклов выполнено: %d)", done)
