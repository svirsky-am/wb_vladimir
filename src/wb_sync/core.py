"""Общая логика sync и построения реестра — для CLI, службы и MCP."""
import logging
from datetime import date, timedelta

from . import db
from .wb_api import WBClient

logger = logging.getLogger(__name__)


def fetch_all(client: WBClient, date_from: date, date_to: date) -> dict:
    """Параллельная выгрузка всех эндпойнтов. Упавшая задача не роняет остальные."""
    return client.fetch_parallel({
        "orders": lambda: client.get_orders(date_from, date_to),
        "sales": lambda: client.get_sales(date_from, date_to),
        "v3_orders": lambda: client.get_v3_orders(date_from, date_to),
        "cards": lambda: client.get_cards(),
    })


def sync_data(config, client: WBClient | None = None) -> dict:
    client = client or WBClient(config)
    today = date.today()
    date_from = today - timedelta(days=config.fetch_window_days * 3)
    data = fetch_all(client, date_from, today)
    engine = db.make_engine(config)
    counts = {
        "orders": db.upsert_orders(engine, data.get("orders") or []),
        "sales": db.upsert_sales(engine, data.get("sales") or []),
        "fbs_orders": db.upsert_fbs_orders(engine, data.get("v3_orders") or [], client),
        "cards": db.upsert_cards(engine, data.get("cards") or []),
    }
    logger.info("Sync завершён: %s", counts)
    return counts


def build_registry_rows(engine, date_from: date, date_to: date) -> list[dict]:
    """Строки реестра: статус из fbs_orders (v3), fallback по isCancel."""
    fbs = {r["srid"]: r for r in db.load_fbs_orders(engine, date_from, date_to)}
    rows = []
    for o in db.load_orders(engine, date_from, date_to):
        f = fbs.get(o["srid"])
        status = f["status"] if f and f.get("status") else ("Отменен" if o.get("isCancel") else "Доставлен")
        rows.append({
            "Магазин": "ИП Олейник",
            "Номер отправления": o["srid"],
            "Статус": status,
            "Принят": o["date"].isoformat() if o.get("date") else "",
            "Артикул": o.get("article") or "",
            "Название товара": o.get("name") or "",
            "Стоимость": round(o.get("finishedPrice", 0) / 100, 2),
            "Склад": "Наш склад Владимир",
        })
    return rows


def build_summary(engine, date_from: date, date_to: date) -> dict:
    sales = db.load_sales(engine, date_from, date_to)
    active = [s for s in sales if not s.get("isCancel")]
    total = sum(s.get("finished_price") or 0 for s in active)
    by_day: dict = {}
    by_article: dict = {}
    for s in active:
        d = s["date"].isoformat() if s.get("date") else ""
        by_day[d] = by_day.get(d, 0.0) + (s.get("finished_price") or 0)
        art = s.get("article") or ""
        agg = by_article.setdefault(art, {"count": 0, "revenue": 0.0})
        agg["count"] += 1
        agg["revenue"] += s.get("finished_price") or 0
    return {"period": (str(date_from), str(date_to)), "total_revenue": round(total, 2),
            "sales_count": len(active), "by_day": by_day, "by_article": by_article}
