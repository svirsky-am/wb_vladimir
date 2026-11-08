"""MCP-сервер wb_sync: инструменты для агента."""

import json
from datetime import date, timedelta

from wb_sync.app_config import AppConfig
from wb_sync import db
from wb_sync.logging_setup import setup_logging
from wb_sync.wb_api import WBClient
from wb_sync.core import sync_data, build_registry_report

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp нужен только для запуска сервера
    FastMCP = None

mcp = FastMCP("wb-sync") if FastMCP else None

_config = None
_engine = None
_client = None


def _ctx():
    global _config, _engine, _client
    if _config is None:
        _config = AppConfig()
        setup_logging(_config)
        _engine = db.make_engine(_config)
        db.init_db(_engine)
        _client = WBClient(_config)
    return _config, _engine, _client


if mcp:
    @mcp.tool()
    def ping_wb() -> str:
        """Проверка доступности WB API."""
        _, _, client = _ctx()
        return json.dumps(client.ping(), ensure_ascii=False)

    @mcp.tool()
    def sync_data_tool(days: int = 30) -> str:
        """Синхронизация данных WB за последние N дней."""
        config, engine, client = _ctx()
        d_to = date.today()
        result = sync_data(config, engine, client, d_to - timedelta(days=days - 1), d_to)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    def build_registry_report_tool(days: int = 30, out_path: str = "") -> str:
        """Построить xlsx-реестр за последние N дней."""
        config, engine, client = _ctx()
        d_to = date.today()
        d_from = d_to - timedelta(days=days - 1)
        path = out_path or str(config.work_dir / f"registry_{d_from}_{d_to}.xlsx")
        build_registry_report(config, engine, client, d_from, d_to, path)
        return path

    @mcp.tool()
    def build_summary_tool(days: int = 30) -> str:
        """Сводка по дням и артикулам за последние N дней (текстом)."""
        _, engine, _ = _ctx()
        d_to = date.today()
        d_from = d_to - timedelta(days=days - 1)
        sales = db.load_sales(engine, d_from, d_to)
        by_day = {}
        for s in sales:
            day = (s.get("date") or "")[:10]
            agg = by_day.setdefault(day, {"count": 0, "sum": 0.0})
            agg["count"] += 1
            agg["sum"] += s.get("finished_price", 0.0)
        return json.dumps(by_day, ensure_ascii=False)

    @mcp.tool()
    def upload_report_to_sheets_tool(file_path: str) -> str:
        """Загрузить xlsx-файл в Google Sheets (нужен GOOGLE_SHEET_ID)."""
        from wb_sync.sheets import upload_file
        config, _, _ = _ctx()
        upload_file(config, file_path)
        return f"Загружено: {file_path}"


if __name__ == "__main__":
    import os
    if os.environ.get("MCP_TRANSPORT") == "streamable-http":
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
