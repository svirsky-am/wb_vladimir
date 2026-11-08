import logging
from logging.handlers import RotatingFileHandler

from wb_sync.app_config import AppConfig

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_configured = False


def setup_logging(config: AppConfig) -> logging.Logger:
    """Лог в work_dir/wb_sync.log (ротация 5 МБ x 5 файлов) + в консоль."""
    global _configured
    root = logging.getLogger()
    if _configured:
        for h in list(root.handlers):
            root.removeHandler(h)
        _configured = False

    root.setLevel(logging.INFO)
    fmt = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(
        config.work_dir / "wb_sync.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    _configured = True
    return logging.getLogger("wb_sync")
