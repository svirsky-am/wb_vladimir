"""MCP-сервер: ping_wb, sync_data, build_registry_report, build_summary."""

import os
from datetime import date

from .app_config import AppConfig
from .logging_setup import setup_logging
from .core import sync_data, build_registry_report, default_window
from .wb_api import WBClient
from . import db
from .reports import build_registry_rows

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("wb-sync")


@mcp.tool()
def ping_wb() -> dict:
    """Проверка доступности WB API."""
    client = WBClient(AppConfig())
    return client.ping()


@mcp.tool()
def sync_data_tool(fetch: bool | None = None) -> dict:
    """Выгрузка отчётов WB и апсерт в SQLite. fetch переопределяет fetch_data из конфига."""
    cfg = AppConfig()
    if fetch is not None:
        cfg.fetch_data = fetch
    return sync_data(cfg)


@mcp.tool()
def build_registry_report_tool(date_from: str | None = None, date_to: str | None = None) -> str:
    """Построить xlsx-реестр за период. Без дат — окно fetch_window_days."""
    cfg = AppConfig()
    df = date.fromisoformat(date_from) if date_from else None
    dt = date.fromisoformat(date_to) if date_to else None
    if df is None or dt is None:
        df, dt = default_window(cfg)
    return build_registry_report(cfg, df, dt)


@mcp.tool()
def build_summary(date_from: str | None = None, date_to: str | None = None) -> dict:
    """Сводка: итоги по дням и артикулам (в виде словаря, без xlsx)."""
    cfg = AppConfig()
    df = date.fromisoformat(date_from) if date_from else None
    dt = date.fromisoformat(date_to) if date_to else None
    if df is None or dt is None:
        df, dt = default_window(cfg)
    engine = db.create_engine_for(cfg)
    db.init_db(engine)
    sales = db.load_sales(engine, df, dt)
    daily, arts = {}, {}
    for s in sales:
        d = daily.setdefault(s["date"], {"count": 0, "revenue": 0.0, "cancels": 0})
        d["count"] += 1
        d["revenue"] += s["finished_price"]
        d["cancels"] += int(bool(s["is_cancel"]))
        a = arts.setdefault(s["article"], {"count": 0, "revenue": 0.0, "cancels": 0})
        a["count"] += 1
        a["revenue"] += s["finished_price"]
        a["cancels"] += int(bool(s["is_cancel"]))
    return {"period": [str(df), str(dt)], "by_day": daily, "by_article": arts}


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    cfg = AppConfig()
    setup_logging(cfg)
    mcp.run(transport=transport)
