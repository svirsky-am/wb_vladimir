"""Выгрузка реестра в Google Sheets (сервисный аккаунт).

Установка: uv sync --extra sheets
Нужны: google_sheet_id и google_credentials_file в конфиге/env
(GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE).
Сервисному аккаунту выдайте доступ к таблице (editor) по его email.
"""
from __future__ import annotations

import os

from .app_config import AppConfig


def upload_xlsx_to_sheets(config: AppConfig, xlsx_path: str, worksheet_title: str = "Реестр") -> str:
    import gspread
    from google.oauth2.service_account import Credentials
    import pandas as pd

    sheet_id = config.google_sheet_id or os.environ.get("GOOGLE_SHEET_ID", "")
    creds_file = config.google_credentials_file or os.environ.get("GOOGLE_CREDENTIALS_FILE", "")
    if not sheet_id or not creds_file:
        raise RuntimeError("Задайте GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_FILE (.staff/env)")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    df = pd.read_excel(xlsx_path, sheet_name="Реестр")
    values = [df.columns.tolist()] + df.fillna("").astype(str).values.tolist()

    titles = [w.title for w in sh.worksheets()]
    if worksheet_title in titles:
        ws = sh.worksheet(worksheet_title)
    else:
        ws = sh.add_worksheet(worksheet_title, rows=len(values) + 10, cols=max((len(r) for r in values), default=10))
    ws.clear()
    ws.update(values)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}"
