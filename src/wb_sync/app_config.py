"""Конфигурация приложения."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from .logging_setup import setup_logging


@dataclass()
class AppConfig:
    work_dir: Path = Path("work_dir")
    api_token: str = field(default="", repr=False)
    fetch_data: bool = True          # env: FETCH_DATA=0 — работать только из кеша
    fetch_interval_minutes: int = 30 # env: FETCH_INTERVAL_MINUTES — пауза службы
    fetch_window_days: int = 30      # окно выгрузки за один чанк
    fetch_workers: int = 3           # env: FETCH_WORKERS — размер пула потоков
    database_file: str = "wb_sync.db"  # относительно work_dir
    sandbox: bool = False            # env: WB_SANDBOX=1 — *-api-sandbox.wildberries.ru
    min_request_interval: float = 1.0  # env: MIN_REQUEST_INTERVAL — троттлинг, с
    max_retries: int = 5             # env: MAX_RETRIES — число повторов при 429/5xx
    retry_base_delay: float = 5.0    # env: RETRY_BASE_DELAY — база экспоненты, с
    log_file: str = "wb_sync.log"    # относительно work_dir

    def __post_init__(self):
        self.work_dir = Path(self.work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        if not self.api_token:
            self.api_token = os.environ.get("API_TOKEN", "")
            if not self.api_token:
                raise ValueError("Критическая ошибка: переменная окружения \'API_TOKEN\' не задана!")
        self.fetch_data = self._env_bool("FETCH_DATA", self.fetch_data)
        self.sandbox = self._env_bool("WB_SANDBOX", self.sandbox)
        self.fetch_interval_minutes = self._env_int("FETCH_INTERVAL_MINUTES", self.fetch_interval_minutes)
        self.fetch_window_days = self._env_int("FETCH_WINDOW_DAYS", self.fetch_window_days)
        self.fetch_workers = self._env_int("FETCH_WORKERS", self.fetch_workers)
        self.min_request_interval = float(os.environ.get("MIN_REQUEST_INTERVAL", self.min_request_interval))
        self.max_retries = self._env_int("MAX_RETRIES", self.max_retries)
        self.retry_base_delay = float(os.environ.get("RETRY_BASE_DELAY", self.retry_base_delay))
        if self.fetch_interval_minutes <= 0:
            raise ValueError("fetch_interval_minutes должен быть > 0")
        if self.fetch_window_days <= 0:
            raise ValueError("fetch_window_days должен быть > 0")
        if self.fetch_workers < 1:
            raise ValueError("fetch_workers должен быть >= 1")
        setup_logging(self.work_dir / self.log_file)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip() not in ("0", "false", "False", "no", "")

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.environ.get(name)
        return default if raw is None else int(raw)

    @property
    def database_path(self) -> Path:
        return self.work_dir / self.database_file
