"""Общая логика: синхронизация данных и сборка реестра."""

import logging
from datetime import date

from wb_sync import db
from wb_sync.reports import build_registry_xlsx

logger = logging.getLogger("wb_sync.core")


def sync_data(config, engine, client, d_from: date, d_to: date):
    """Полный цикл выгрузки: v1 statistics + v3 FBS + карточки -> БД."""
    logger.info("Синхронизация %s..%s (fetch_data=%s)", d_from, d_to, config.fetch_data)
    result = {}
    result["orders"] = db.upsert_orders(engine, client.get_orders(d_from, d_to))
    result["sales"] = db.upsert_sales(engine, client.get_sales(d_from, d_to))
    result["fbs_orders"] = db.upsert_fbs_orders(engine, client.get_v3_orders(d_from, d_to), client)
    try:
        result["cards"] = db.upsert_cards(engine, client.get_cards())
    except Exception:
        logger.exception("Не удалось выгрузить карточки — пропускаю, продолжаю")
        result["cards"] = 0
    logger.info("Синхронизация завершена: %s", result)
    return result


def build_registry_report(config, engine, client, d_from: date, d_to: date, out_path):
    orders = db.load_orders(engine, d_from, d_to)
    fbs = {r["rid"]: r for r in db.load_fbs_orders(engine, d_from, d_to)}
    sales = db.load_sales(engine, d_from, d_to)
    return build_registry_xlsx(
        orders, sales, fbs, out_path,
        shop_name="ИП Олейник",
    )
