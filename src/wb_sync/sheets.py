"""Выгрузка xlsx в Google Sheets (сервисный аккаунт)."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def upload_to_sheets(config, file_path: Path, sheet_name: str = "Реестр") -> str:
    """Требует GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_FILE в окружении."""
    import gspread
    from google.oauth2.service_account import Credentials

    sheet_id = __import__("os").environ.get("GOOGLE_SHEET_ID")
    creds_file = __import__("os").environ.get("GOOGLE_CREDENTIALS_FILE")
    if not sheet_id or not creds_file:
        raise ValueError("Нужны переменные окружения GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_FILE")
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_name) if sheet_name in [w.title for w in sh.worksheets()] else sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    from openpyxl import load_workbook
    wb = load_workbook(Path(file_path), data_only=True)
    source = wb.active
    values = [[("" if c is None else c) for c in row] for row in source.iter_rows(values_only=True)]
    ws.clear()
    ws.update(values=values, range_name="A1")
    logger.info("Выгружено в Google Sheets %s / лист %s: %d строк", sheet_id, sheet_name, len(values))
    return f"Выгружено в Google Sheets: {len(values)} строк, лист {sheet_name}"
