import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass()
class AppConfig:
    """Конфигурация приложения. Поля переопределяются переменными окружения."""

    work_dir: Path = "work_dir"
    api_token: str = field(default="", repr=False)
    api_url: str = "https://example.com"
    # Выгружать ли данные из API (False — работать только с кешем в work_dir)
    fetch_data: bool = True
    # Период фетча для службы, минут (env: FETCH_INTERVAL_MINUTES)
    fetch_interval_minutes: float = 30.0
    # Окно выгрузки за один цикл, дней (лимиты WB: не более 30 на запрос)
    fetch_window_days: int = 30
    # Файл БД относительно work_dir
    database_path: str = "wb_sync.db"
    # Минимальная пауза между запросами к WB, сек (троттлинг)
    min_request_interval: float = 1.0
    # Ретраи при 429/5xx и базовая задержка экспоненциального backoff, сек
    max_retries: int = 5
    retry_base_delay: float = 5.0
    # Песочница WB (WB_SANDBOX=1) — хосты *-api-sandbox.wildberries.ru
    sandbox: bool = False

    def __post_init__(self):
        self.work_dir = Path(self.work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_token:
            token_from_env = os.environ.get("API_TOKEN")
            if not token_from_env:
                raise ValueError(
                    "Критическая ошибка: Переменная окружения 'API_TOKEN' не задана!"
                )
            self.api_token = token_from_env

        env_fetch = os.environ.get("FETCH_DATA")
        if env_fetch is not None:
            self.fetch_data = env_fetch.strip().lower() not in ("0", "false", "no")

        env_interval = os.environ.get("FETCH_INTERVAL_MINUTES")
        if env_interval:
            self.fetch_interval_minutes = float(env_interval)
        if self.fetch_interval_minutes <= 0:
            raise ValueError("fetch_interval_minutes должен быть больше 0")
        if self.fetch_window_days < 1 or self.fetch_window_days > 30:
            raise ValueError("fetch_window_days должен быть в диапазоне 1..30")

        env_sandbox = os.environ.get("WB_SANDBOX")
        if env_sandbox is not None:
            self.sandbox = env_sandbox.strip().lower() in ("1", "true", "yes")

        if not os.path.isabs(self.database_path):
            self.database_path = str(self.work_dir / self.database_path)
