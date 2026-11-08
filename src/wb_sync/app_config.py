import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass()
class AppConfig:
    work_dir: Path = "work_dir"
    api_token: str = field(default="", repr=False)
    api_url: str = "https://statistics-api.wildberries.ru"
    # Периодический фетч: True — служба сама выкачивает данные, False — работает по кешу
    fetch_data: bool = True
    # Интервал цикла фетча для службы (минуты)
    fetch_interval_minutes: int = 30
    # Окно выгрузки за один цикл (дни, максимум 30 для statistics-api)
    fetch_window_days: int = 30
    database_path: str = "wb_sync.db"

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

        # Переопределение из окружения (удобно для службы и агента)
        env_fetch = os.environ.get("FETCH_DATA")
        if env_fetch is not None:
            self.fetch_data = env_fetch.strip().lower() not in ("0", "false", "no")

        env_interval = os.environ.get("FETCH_INTERVAL_MINUTES")
        if env_interval:
            self.fetch_interval_minutes = int(env_interval)

        if self.fetch_interval_minutes <= 0:
            raise ValueError("fetch_interval_minutes должен быть положительным")
        if not 1 <= self.fetch_window_days <= 30:
            raise ValueError("fetch_window_days должен быть в диапазоне 1..30")

    @property
    def database_file(self) -> Path:
        db_path = Path(self.database_path)
        return db_path if db_path.is_absolute() else self.work_dir / db_path

    @property
    def log_file(self) -> Path:
        return self.work_dir / "wb_sync.log"
