from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED_PATHS: set = set()


def setup_logging(work_dir) -> None:
    """Лог в work_dir/wb_sync.log (ротация 5 МБ x 5) + дублируется в консоль."""
    log_path = (Path(work_dir) / "wb_sync.log").resolve()
    if log_path in _CONFIGURED_PATHS:
        return
    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(console)
    _CONFIGURED_PATHS.add(log_path)
