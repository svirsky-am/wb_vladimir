import logging
from logging.handlers import RotatingFileHandler

from .app_config import AppConfig

_FORMAT = "%(asctime)s %(levelname)s %(name)s :: %(message)s"


def setup_logging(app_config: AppConfig, level: int = logging.INFO) -> logging.Logger:
    """Лог в work_dir/wb_sync.log (ротация 5 МБ, 5 файлов) + консоль."""
    logger = logging.getLogger("wb_sync")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        app_config.log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger
