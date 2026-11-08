"""Общая логика sync + отчёт: используется CLI, службой и MCP-сервером."""

import logging
from datetime import date, timedelta

from .app_config import AppConfig
from .wb_api import WBClient
from . import db
from .reports import build_registry_rows, write_registry_xlsx

logger = logging.getLogger("wb_sync.core")


def default_window(app_config: AppConfig):
    date_to = date.today()
    date_from = date_to - timedelta(days=app_config.fetch_window_days - 1)
    return date_from, date_to


def sync_data(
    app_config: AppConfig,
    client: WBClient | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """Выгрузка (или чтение кеша) + апсерт в SQLite. Возвращает счётчики."""
    if date_from is None or date_to is None:
        date_from, date_to = default_window(app_config)
    client = client or WBClient(app_config)

    if app_config.fetch_data:
        logger.info("Фетч данных WB %s..%s", date_from, date_to)
        orders = client.get_orders(date_from, date_to)
        sales = client.get_sales(date_from, date_to)
        fbs = client.get_fbs_orders(date_from, date_to)
    else:
        logger.info("Чтение кеша %s..%s (fetch_data=False)", date_from, date_to)
        orders = client.load_orders(date_from, date_to)
        sales = client.load_sales(date_from, date_to)
        fbs = client.load_fbs_orders(date_from, date_to)

    engine = db.create_engine_for(app_config)
    db.init_db(engine)
    n_orders = db.upsert_orders(engine, orders)
    n_sales = db.upsert_sales(engine, sales)
    n_fbs = db.upsert_fbs_orders(engine, fbs, client)
    logger.info(
        "Синхронизация завершена: orders +%d, sales +%d, fbs +%d",
        n_orders, n_sales, n_fbs,
    )
    return {"orders": len(orders), "sales": len(sales), "fbs": len(fbs),
            "new_orders": n_orders, "new_sales": n_sales, "new_fbs": n_fbs}


def build_registry_report(
    app_config: AppConfig,
    date_from: date,
    date_to: date,
    out_path: str | None = None,
) -> str:
    """Сборка xlsx-реестра из БД."""
    engine = db.create_engine_for(app_config)
    db.init_db(engine)
    orders = db.load_orders(engine, date_from, date_to)
    sales = db.load_sales(engine, date_from, date_to)
    fbs_rows = db.load_fbs_orders(engine, date_from, date_to)
    fbs_by_srid = {r["srid"]: r for r in fbs_rows}

    rows = build_registry_rows(orders, fbs_by_srid)
    out = out_path or str(app_config.work_dir / f"wb_registry_{date_from}_{date_to}.xlsx")
    path = write_registry_xlsx(rows, out, sales=sales)
    logger.info("Отчёт сохранён: %s (строк: %d)", path, len(rows))
    return str(path)
