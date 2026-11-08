"""CLI wb-sync."""
from __future__ import annotations

import argparse
import asyncio
from datetime import date

from .app_config import AppConfig
from .core import sync_cards, sync_data
from .db import get_engine, load_fbs_orders, load_orders
from .logging_setup import setup_logging
from .reports import build_registry_rows, build_registry_xlsx
from .wb_api import WBClient


def main():
    parser = argparse.ArgumentParser(prog="wb-sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--date-from", required=True)
    p_sync.add_argument("--date-to", required=True)
    p_sync.add_argument("--no-fetch", action="store_true")

    p_cards = sub.add_parser("cards")
    p_cards.add_argument("--no-fetch", action="store_true")

    p_report = sub.add_parser("report")
    p_report.add_argument("--date-from", required=True)
    p_report.add_argument("--date-to", required=True)
    p_report.add_argument("--out", default="work_dir/registry.xlsx")

    p_sheets = sub.add_parser("upload-sheets")
    p_sheets.add_argument("--file", required=True)
    p_sheets.add_argument("--worksheet", default="Реестр")

    sub.add_parser("serve")

    args = parser.parse_args()
    config = AppConfig()
    setup_logging(config.work_dir)

    if args.cmd == "serve":
        from .service import run_service
        asyncio.run(run_service(config))
        return

    if args.no_fetch:
        config.fetch_data = False

    client = WBClient(config)
    engine = get_engine(config)

    if args.cmd == "sync":
        print(sync_data(config, engine, client))
    elif args.cmd == "cards":
        print(sync_cards(config, engine, client))
    elif args.cmd == "report":
        d1, d2 = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)
        fbs = {r["srid"]: r for r in load_fbs_orders(engine, d1, d2)}
        rows = build_registry_rows(load_orders(engine, d1, d2), fbs)
        out = build_registry_xlsx(rows, d1, d2, args.out)
        print(f"Отчёт: {out} ({len(rows)} строк)")
    elif args.cmd == "upload-sheets":
        from .sheets import upload_xlsx_to_sheets
        print(upload_xlsx_to_sheets(config, args.file, args.worksheet))


if __name__ == "__main__":
    main()
