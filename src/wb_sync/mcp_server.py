"""MCP-сервер: регистрируется в MCP Hub (Yandex AI Studio) или запускается локально.

Инструменты записи в WB (update_cards/create_cards) НЕ выведены как MCP-инструменты
намеренно: изменение карточек — критическое действие, выполняйте вручную через CLI/код.
"""
from __future__ import annotations

import os
from datetime import date

from mcp.server.fastmcp import FastMCP

from .app_config import AppConfig
from .core import sync_cards, sync_data
from .db import get_engine, load_fbs_orders, load_orders
from .logging_setup import setup_logging
from .reports import build_registry_rows, build_registry_xlsx
from .wb_api import WBClient

mcp = FastMCP("wb-sync")

if os.environ.get("MCP_TRANSPORT") == "streamable-http":
    mcp.settings.port = int(os.environ.get("MCP_PORT", "8080"))


def _boot(no_fetch: bool = False):
    config = AppConfig()
    setup_logging(config.work_dir)
    if no_fetch:
        config.fetch_data = False
    return config, get_engine(config), WBClient(config)


@mcp.tool()
def ping_wb() -> str:
    """Проверка связи с WB API."""
    config, _, client = _boot()
    r = client.session.get(client.common_base + "/ping", timeout=30)
    return f"HTTP {r.status_code}: {r.text[:200]}"


@mcp.tool()
def sync_data_tool() -> str:
    """Выгрузить заказы/продажи/FBS-заказы из WB и записать в локальную БД."""
    config, engine, client = _boot()
    return str(sync_data(config, engine, client))


@mcp.tool()
def sync_cards_tool() -> str:
    """Выгрузить карточки товаров из WB и записать в БД."""
    config, engine, client = _boot()
    return str(sync_cards(config, engine, client))


@mcp.tool()
def build_registry_report_tool(date_from: str, date_to: str, out: str = "work_dir/registry.xlsx") -> str:
    """Построить xlsx-реестр отгрузок за период из локальной БД (без обращения к API)."""
    config, engine, _ = _boot(no_fetch=True)
    d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    fbs = {r["srid"]: r for r in load_fbs_orders(engine, d1, d2)}
    rows = build_registry_rows(load_orders(engine, d1, d2), fbs)
    build_registry_xlsx(rows, d1, d2, out)
    return f"{out}: {len(rows)} строк"


@mcp.tool()
def build_summary_tool(date_from: str, date_to: str) -> str:
    """Текстовая сводка за период: выручка, позиции, отмены по дням и артикулам."""
    config, engine, _ = _boot(no_fetch=True)
    d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    fbs = {r["srid"]: r for r in load_fbs_orders(engine, d1, d2)}
    rows = build_registry_rows(load_orders(engine, d1, d2), fbs)
    total = sum(r["Стоимость"] for r in rows if r["Статус"] != "Отменен")
    cancels = sum(1 for r in rows if r["Статус"] == "Отменен")
    return f"Строк: {len(rows)}, выручка: {total:.2f} ₽, отмен: {cancels}"


@mcp.tool()
def upload_report_to_sheets_tool(xlsx_path: str, worksheet: str = "Реестр") -> str:
    """Выгрузить xlsx-реестр в Google Sheets (нужны GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_FILE)."""
    from .sheets import upload_xlsx_to_sheets
    config, _, _ = _boot(no_fetch=True)
    return upload_xlsx_to_sheets(config, xlsx_path, worksheet)


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
