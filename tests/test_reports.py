from datetime import date

from openpyxl import load_workbook

from wb_sync import db
from wb_sync.app_config import AppConfig
from wb_sync.db import make_engine
from wb_sync.reports import build_xlsx


def make_cfg(tmp_path):
    import os
    os.environ.setdefault("API_TOKEN", "tok")
    return AppConfig(work_dir=tmp_path)


def test_registry_rows_use_fbs_status(tmp_path):
    cfg = make_cfg(tmp_path)
    engine = make_engine(cfg)
    db.upsert_orders(engine, [{"srid": "s1", "date": "2026-10-05", "supplierArticle": "A", "goodsName": "N", "finishedPrice": 2900000}])
    db.upsert_fbs_orders(engine, [{"rid": "s1", "article": "A", "price": 29000, "createdAt": 1761500000000,
                                   "statuses": {"isCancel": False, "supplierStatus": "delivered"}}], None)
    rows = __import__("wb_sync.core", fromlist=["build_registry_rows"]).build_registry_rows(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert rows[0]["Статус"] == "Доставлен"


def test_registry_rows_fallback(tmp_path):
    cfg = make_cfg(tmp_path)
    engine = make_engine(cfg)
    db.upsert_orders(engine, [{"srid": "s2", "date": "2026-10-05", "supplierArticle": "A", "goodsName": "N", "finishedPrice": 100000, "isCancel": False}])
    rows = __import__("wb_sync.core", fromlist=["build_registry_rows"]).build_registry_rows(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert rows[0]["Статус"] == "Доставлен"


def test_xlsx_structure(tmp_path):
    out = build_xlsx(
        [{"Магазин": "ИП Олейник", "Номер отправления": "1", "Статус": "Доставлен",
          "Принят": "2026-10-05", "Артикул": "A", "Название товара": "N", "Стоимость": 29548.0, "Склад": "X"}],
        {"2026-10-05": 29548.0}, {"A": {"count": 1, "revenue": 29548.0}}, tmp_path / "r.xlsx")
    wb = load_workbook(out)
    assert wb.sheetnames == ["Реестр", "По дням", "По артикулам"]
    assert wb["Реестр"].max_row == 2


def test_empty_rows(tmp_path):
    out = build_xlsx([], {}, {}, tmp_path / "empty.xlsx")
    wb = load_workbook(out)
    assert wb["Реестр"].max_row == 1
