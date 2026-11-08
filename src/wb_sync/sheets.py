"""Выгрузка xlsx в Google Sheets (сервисный аккаунт)."""

import json
import logging
import os

logger = logging.getLogger("wb_sync.sheets")


def upload_file(config, file_path: str):
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")
    if not sheet_id or not creds_file:
        raise RuntimeError(
            "Нужны переменные окружения GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_FILE "
            "(см. README, раздел Google Sheets)"
        )
    import gspread
    gc = gspread.service_account(filename=creds_file)
    sh = gc.open_by_key(sheet_id)
    logger.info("Загрузка %s в Google Sheets %s", file_path, sheet_id)

    from openpyxl import load_workbook
    wb = load_workbook(file_path, data_only=True)
    for ws in wb.worksheets:
        try:
            worksheet = sh.worksheet(ws.title)
        except Exception:
            worksheet = sh.add_worksheet(title=ws.title, rows=100, cols=26)
        rows = [[c for c in row] for row in ws.iter_rows(values_only=True)]
        worksheet.clear()
        worksheet.update(range_name="A1", values=rows)
        logger.info("Лист «%s»: %d строк", ws.title, len(rows))
