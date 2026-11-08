from datetime import date

from wb_sync import db
from wb_sync.app_config import AppConfig
from wb_sync.db import make_engine


def make_cfg(tmp_path):
    import os
    os.environ.setdefault("API_TOKEN", "tok")
    return AppConfig(work_dir=tmp_path)


def test_upsert_orders_idempotent(tmp_path):
    engine = make_engine(make_cfg(tmp_path))
    rows = [{"srid": "s1", "date": "2026-10-05", "supplierArticle": "MC12", "goodsName": "N", "finishedPrice": 100000}]
    assert db.upsert_orders(engine, rows) == 1
    assert db.upsert_orders(engine, rows) == 0
    assert len(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))) == 1


def test_upsert_sales_kopecks(tmp_path):
    engine = make_engine(make_cfg(tmp_path))
    row = {"saleID": "sa1", "date": "2026-10-06", "srid": "s1",
           "supplierArticle": "MC12", "finishedPrice": 2954800, "isCancel": False}
    db.upsert_sales(engine, [row])
    loaded = db.load_sales(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert loaded[0]["finished_price"] == 29548.0


def test_fbs_upsert(tmp_path):
    from wb_sync.wb_api import WBClient
    client = WBClient(make_cfg(tmp_path))
    row = {"rid": "r1", "article": "MC12", "price": 29548.0, "createdAt": 1761500000000,
           "statuses": {"isCancel": False, "supplierStatus": "delivering"}}
    engine = make_engine(make_cfg(tmp_path))
    assert db.upsert_fbs_orders(engine, [row], client) == 1
    assert db.upsert_fbs_orders(engine, [row], client) == 0
    loaded = db.load_fbs_orders(engine, date(2025, 10, 21), date(2025, 10, 29))
    assert loaded[0]["status"] == "Доставляется"


def test_date_filter(tmp_path):
    engine = make_engine(make_cfg(tmp_path))
    db.upsert_orders(engine, [
        {"srid": "a", "date": "2026-10-05", "finishedPrice": 100},
        {"srid": "b", "date": "2026-09-05", "finishedPrice": 100},
    ])
    assert len(db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))) == 1
