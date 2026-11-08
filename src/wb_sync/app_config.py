from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .logging_setup import setup_logging


@dataclass()
class AppConfig:
    work_dir: Path = "work_dir"
    api_token: str = field(default="", repr=False)
    # Периодический фетч
    fetch_data: bool = True
    fetch_interval_minutes: int = 30
    fetch_window_days: int = 30
    # Песочница WB: True -> все хосты меняются на *-api-sandbox.wildberries.ru
    sandbox: bool = False
    # БД и логи живут в work_dir
    database_path: Path = "wb_sync.db"
    # Выгрузка в Google Sheets (необязательно)
    google_sheet_id: str = ""
    google_credentials_file: str = ""

    def __post_init__(self):
        self.work_dir = Path(self.work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        setup_logging(self.work_dir)

        self.responses_dir = self.work_dir / "responses"
        self.responses_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_token:
            token_from_env = os.environ.get("API_TOKEN")
            if not token_from_env:
                raise ValueError("Критическая ошибка: Переменная окружения 'API_TOKEN' не задана!")
            self.api_token = token_from_env

        if os.environ.get("FETCH_DATA") is not None:
            self.fetch_data = os.environ["FETCH_DATA"].lower() not in ("0", "false", "no")
        if os.environ.get("WB_SANDBOX") is not None:
            self.sandbox = os.environ["WB_SANDBOX"].lower() in ("1", "true", "yes")
        if os.environ.get("FETCH_INTERVAL_MINUTES") is not None:
            self.fetch_interval_minutes = int(os.environ["FETCH_INTERVAL_MINUTES"])
        if self.fetch_interval_minutes <= 0:
            raise ValueError("fetch_interval_minutes должен быть > 0")
        if self.fetch_window_days <= 0:
            raise ValueError("fetch_window_days должен быть > 0")

        self.database_path = Path(self.database_path)
        if not self.database_path.is_absolute():
            self.database_path = self.work_dir / self.database_path
