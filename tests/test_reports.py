from datetime import date

import pytest
from sqlalchemy import create_engine

from wb_sync import db, reports
from wb_sync.app_config import AppConfig


@pytest.fixture()
def engine(tmp_path):
    cfg = AppConfig(work_dir=str(tmp_path / "wd"), api_token="tok", database_path="wb_sync.db")
    eng = db.get_engine(cfg)
    yield eng
    eng.dispose()


def _fill(engine):
    from wb_sync.wb_api import WBClient
    client = WBClient(AppConfig(work_dir="/tmp/_wb_probe2", api_token="tok"))
    db.upsert_orders(engine, [
        {"srid": "r1", "date": "2026-10-05T00:00:00", "supplierArticle": "MC12",
         "subjectName": "Пылесос", "warehouseName": "Владимир", "finishedPrice": 2954800, "isCancel": False},
    ])
    db.upsert_fbs_orders(engine, [
        {"rid": "r1", "nmId": 1, "price": 29548.0, "createdAt": 1791936000000,
         "statuses": {"isCancel": False, "supplierStatus": "delivering"}},
    ], client)


def test_registry_rows_use_fbs_status(engine):
    _fill(engine)
    fbs = {r["srid"]: r for r in db.load_fbs_orders(engine, date(2026, 10, 1), date(2026, 10, 31))}
    rows = reports.build_registry_rows(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31)), fbs)
    assert rows[0]["Статус"] == "Доставляется"
    assert rows[0]["Стоимость"] == 29548.0


def test_registry_rows_fallback(engine):
    db.upsert_orders(engine, [
        {"srid": "r2", "date": "2026-10-06T00:00:00", "supplierArticle": "X",
         "subjectName": "S", "warehouseName": "W", "finishedPrice": 10000, "isCancel": True},
    ])
    rows = reports.build_registry_rows(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31)), {})
    assert rows[0]["Статус"] == "Отменен"


def test_xlsx_structure(engine, tmp_path):
    _fill(engine)
    fbs = {r["srid"]: r for r in db.load_fbs_orders(engine, date(2026, 10, 1), date(2026, 10, 31))}
    rows = reports.build_registry_rows(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31)), fbs)
    out = tmp_path / "registry.xlsx"
    reports.build_registry_xlsx(rows, date(2026, 10, 1), date(2026, 10, 31), str(out))
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert wb.sheetnames == ["Реестр", "По дням", "По артикулам"]
    assert wb["Реестр"]["C2"].value == "Доставляется"


def test_empty_rows(tmp_path):
    out = tmp_path / "empty.xlsx"
    reports.build_registry_xlsx([], date(2026, 10, 1), date(2026, 10, 31), str(out))
    from openpyxl import load_workbook
    wb = load_workbook(out)
    assert wb["Реестр"].max_row == 1
