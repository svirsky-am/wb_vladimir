"""CLI: wb-sync sync|report|all|cards|serve|ping|upload-sheets."""
import argparse
from datetime import date

from .app_config import AppConfig
from .core import build_registry_rows, build_summary, sync_data
from .db import make_engine
from .reports import build_xlsx
from .service import run_service
from .wb_api import WBClient


def _dates(args):
    today = date.today()
    return (getattr(args, "date_from", None) or date(today.year, today.month, 1), getattr(args, "date_to", None) or today)


def main() -> None:
    parser = argparse.ArgumentParser(prog="wb-sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("sync", "report", "all"):
        sp = sub.add_parser(name)
        sp.add_argument("--date-from", type=date.fromisoformat)
        sp.add_argument("--date-to", type=date.fromisoformat)
        sp.add_argument("--out", default=None)
    sub.add_parser("cards")
    sub.add_parser("ping")
    sub.add_parser("serve")
    up = sub.add_parser("upload-sheets")
    up.add_argument("--file", required=True)
    args = parser.parse_args()
    config = AppConfig()

    if args.cmd == "ping":
        print(WBClient(config).ping())
    elif args.cmd == "cards":
        client = WBClient(config)
        engine = make_engine(config)
        print("Карточек добавлено:", _cards_sync(engine, client))
    elif args.cmd == "serve":
        import asyncio
        asyncio.run(run_service(config))
    elif args.cmd == "upload-sheets":
        from .sheets import upload_to_sheets
        print(upload_to_sheets(config, args.file))
    else:
        date_from, date_to = _dates(args)
        if args.cmd in ("sync", "all"):
            print(sync_data(config))
        if args.cmd in ("report", "all"):
            engine = make_engine(config)
            rows = build_registry_rows(engine, date_from, date_to)
            summary = build_summary(engine, date_from, date_to)
            out = args.out or config.work_dir / f"registry_{date_from}_{date_to}.xlsx"
            path = build_xlsx(rows, summary["by_day"], summary["by_article"], out)
            print(f"Отчёт: {path}")
            print(summary["total_revenue"])


def _cards_sync(engine, client) -> int:
    from . import db
    return db.upsert_cards(engine, client.get_cards())


if __name__ == "__main__":
    main()
