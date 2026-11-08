from datetime import date

import pytest
from sqlalchemy import create_engine

from wb_sync import db
from wb_sync.app_config import AppConfig
from wb_sync.wb_api import WBClient


@pytest.fixture()
def engine(tmp_path):
    cfg = AppConfig(work_dir=str(tmp_path / "wd"), api_token="tok", database_path="wb_sync.db")
    eng = db.get_engine(cfg)
    yield eng
    eng.dispose()


def test_upsert_orders_idempotent(engine):
    rows = [{"srid": "1", "date": "2026-10-01T00:00:00", "nmId": 5, "supplierArticle": "A",
             "subjectName": "S", "brandName": "B", "warehouseName": "W",
             "totalPrice": 100000, "discountPercent": 5, "finishedPrice": 95000, "isCancel": False}]
    assert db.upsert_orders(engine, rows) == 1
    assert db.upsert_orders(engine, rows) == 0
    loaded = db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert len(loaded) == 1
    assert loaded[0]["finishedPrice"] == 950.0


def test_upsert_sales_kopecks(engine):
    row = {"saleID": "sa1", "date": "2026-10-06", "srid": "s1",
           "supplierArticle": "MC12", "finishedPrice": 2954800, "isCancel": False}
    db.upsert_sales(engine, [row])
    loaded = db.load_sales(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert loaded[0]["finished_price"] if False else loaded[0]["finishedPrice"] == 29548.0


def test_fbs_upsert(engine):
    from wb_sync.wb_api import WBClient
    client = WBClient(AppConfig(work_dir="/tmp/_wb_probe", api_token="tok"))
    # 2026-10-17 00:00 UTC в миллисекундах
    row = {"rid": "r1", "nmId": 1, "price": 29548.0, "createdAt": 1792195200000,
           "statuses": {"isCancel": False, "supplierStatus": "delivering"}}
    assert db.upsert_fbs_orders(engine, [row], client) == 1
    assert db.upsert_fbs_orders(engine, [row], client) == 0
    loaded = db.load_fbs_orders(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert loaded, "запись должна попадать в диапазон фильтра по дате"
    assert loaded[0]["status"] == "Доставляется"
    assert loaded[0]["price"] == 29548.0


def test_date_filter(engine):
    rows = [
        {"saleID": "a", "date": "2026-10-05", "finishedPrice": 100, "isCancel": False},
        {"saleID": "b", "date": "2026-11-20", "finishedPrice": 200, "isCancel": False},
    ]
    db.upsert_sales(engine, rows)
    assert len(db.load_sales(engine, date(2026, 10, 1), date(2026, 10, 31))) == 1
    assert len(db.load_sales(engine, date(2026, 11, 1), date(2026, 11, 30))) == 1


def test_cards_upsert(engine):
    cards = [{"nmID": 1, "imtID": 10, "vendorCode": "MC12", "brand": "VOXLEN", "title": "Пылесос"}]
    assert db.upsert_cards(engine, cards) == 1
    assert db.upsert_cards(engine, cards) == 0
    loaded = db.load_cards(engine)
    assert loaded[0]["vendorCode"] == "MC12"
    assert loaded[0]["imtID"] == 10
    assert db.load_cards(engine, article="MC12")[0]["nmID"] == 1
