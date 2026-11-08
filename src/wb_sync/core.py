"""Общая логика для CLI, службы и MCP-сервера."""
from __future__ import annotations

from datetime import date, timedelta

from . import db
from .wb_api import WBClient


def sync_data(config, engine, client: WBClient) -> dict:
    end = date.today()
    start = end - timedelta(days=config.fetch_window_days - 1)
    stats = {}
    orders = client.get_orders(start, end)
    stats["orders"] = db.upsert_orders(engine, orders)
    sales = client.get_sales(start, end)
    stats["sales"] = db.upsert_sales(engine, sales)
    fbs = client.get_fbs_orders(start, end)
    stats["fbs_orders"] = db.upsert_fbs_orders(engine, fbs, client)
    return stats


def sync_cards(config, engine, client: WBClient) -> dict:
    cards = client.get_cards()
    return {"cards": db.upsert_cards(engine, cards)}
