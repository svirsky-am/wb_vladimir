"""MCP-сервер: инструменты для агентов AI Studio / Алисы AI Про."""
import os
from datetime import date

from mcp.server.fastmcp import FastMCP

from .app_config import AppConfig
from .core import build_registry_rows, build_summary, sync_data
from .db import make_engine
from .reports import build_xlsx
from .wb_api import WBClient

mcp = FastMCP("wb-sync")


def _cfg() -> AppConfig:
    return AppConfig()


@mcp.tool()
def ping_wb_tool() -> str:
    """Проверка доступности API Wildberries."""
    return str(WBClient(_cfg()).ping())


@mcp.tool()
def sync_data_tool() -> str:
    """Выгрузка данных WB (заказы, продажи, FBS, карточки) в локальную БД."""
    counts = sync_data(_cfg())
    return f"Sync завершён: {counts}"


@mcp.tool()
def build_registry_report_tool(date_from: str, date_to: str) -> str:
    """Построить xlsx-реестр FBS-отгрузок за период и вернуть путь к файлу."""
    config = _cfg()
    engine = make_engine(config)
    d1, d2 = date.fromisoformat(date_from), date.fromisoformat(date_to)
    rows = build_registry_rows(engine, d1, d2)
    summary = build_summary(engine, d1, d2)
    out = config.work_dir / f"registry_{date_from}_{date_to}.xlsx"
    build_xlsx(rows, summary["by_day"], summary["by_article"], out)
    return f"Отчёт сохранён: {out} (строк: {len(rows)}, выручка: {summary['total_revenue']})"


@mcp.tool()
def build_summary_tool(date_from: str, date_to: str) -> str:
    """Сводка по продажам за период: выручка, количество, срезы по дням и артикулам."""
    config = _cfg()
    engine = make_engine(config)
    summary = build_summary(engine, date.fromisoformat(date_from), date.fromisoformat(date_to))
    return str(summary)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
