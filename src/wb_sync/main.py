"""CLI: wb-sync sync|report|all|serve"""

import argparse
import sys
from datetime import date, timedelta

from .app_config import AppConfig
from .logging_setup import setup_logging
from .core import sync_data, build_registry_report, default_window
from .service import serve


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="wb-sync", description=__doc__)
    parser.add_argument("command", choices=["sync", "report", "all", "serve"])
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--out")
    parser.add_argument("--no-fetch", action="store_true", help="работать по кешу в work_dir")
    args = parser.parse_args(argv)

    cfg = AppConfig(fetch_data=not args.no_fetch)
    setup_logging(cfg)

    if args.command == "serve":
        serve(cfg)
        return 0

    date_from, date_to = _parse_date(args.date_from), _parse_date(args.date_to)
    if args.command in ("sync", "all"):
        if date_from is None or date_to is None:
            date_from, date_to = default_window(cfg)
        sync_data(cfg, date_from=date_from, date_to=date_to)
    if args.command in ("report", "all"):
        if date_from is None or date_to is None:
            date_from, date_to = default_window(cfg)
        path = build_registry_report(cfg, date_from, date_to, out_path=args.out)
        print(f"Отчёт: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
