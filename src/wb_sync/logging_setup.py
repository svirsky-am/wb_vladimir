"""Настройка логирования: файл в work_dir + консоль."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def setup_logging(log_path: Path) -> None:
    global _configured
    if _configured:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(fh)
    root.addHandler(sh)
    _configured = True
