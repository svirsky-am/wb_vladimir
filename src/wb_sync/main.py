"""CLI wb-sync: sync | report | cards | serve | upload-sheets."""

import argparse
from datetime import date, timedelta

from wb_sync.app_config import AppConfig
from wb_sync import db
from wb_sync.logging_setup import setup_logging
from wb_sync.wb_api import WBClient
from wb_sync.core import sync_data, build_registry_report


def _parse_args():
    p = argparse.ArgumentParser(prog="wb-sync")
    sub = p.add_subparsers(dest="cmd", required=True)

    def period(sp):
        sp.add_argument("--date-from", type=str, default=None)
        sp.add_argument("--date-to", type=str, default=None)
        sp.add_argument("--no-fetch", action="store_true")

    s_sync = sub.add_parser("sync")
    period(s_sync)

    s_rep = sub.add_parser("report")
    period(s_rep)
    s_rep.add_argument("--out", default=None)

    sub.add_parser("cards")

    s_up = sub.add_parser("upload-sheets")
    s_up.add_argument("--file", required=True)

    sub.add_parser("serve")
    return p.parse_args()


def main():
    args = _parse_args()
    config = AppConfig()
    if getattr(args, "no_fetch", False):
        config.fetch_data = False
    setup_logging(config)

    engine = db.make_engine(config)
    db.init_db(engine)
    client = WBClient(config)

    if args.cmd == "sync":
        d_to = date.fromisoformat(args.date_to) if args.date_to else date.today()
        d_from = date.fromisoformat(args.date_from) if args.date_from else d_to - timedelta(days=29)
        result = sync_data(config, engine, client, d_from, d_to)
        print(result)
    elif args.cmd == "report":
        d_to = date.fromisoformat(args.date_to) if args.date_to else date.today()
        d_from = date.fromisoformat(args.date_from) if args.date_from else d_to - timedelta(days=29)
        out = args.out or str(config.work_dir / f"registry_{d_from}_{d_to}.xlsx")
        build_registry_report(config, engine, client, d_from, d_to, out)
        print(f"Отчёт: {out}")
    elif args.cmd == "cards":
        cards = client.get_cards()
        added = db.upsert_cards(engine, cards)
        print(f"Карточек в ответе: {len(cards)}, новых: {added}")
    elif args.cmd == "upload-sheets":
        from wb_sync.sheets import upload_file
        upload_file(config, args.file)
        print("Загружено в Google Sheets")
    elif args.cmd == "serve":
        from wb_sync.service import main as serve_main
        serve_main()


if __name__ == "__main__":
    main()
