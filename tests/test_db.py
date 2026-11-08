from datetime import date

import pytest

from wb_sync.app_config import AppConfig
from wb_sync import db


@pytest.fixture
def engine(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "tok")
    cfg = AppConfig(work_dir=tmp_path)
    eng = db.create_engine_for(cfg)
    db.init_db(eng)
    return eng


def test_upsert_orders_idempotent(engine):
    row = {"srid": "s1", "date": "2026-10-05T10:00:00", "supplierArticle": "MC12",
           "finishedPrice": 28070.60, "isCancel": False}
    assert db.upsert_orders(engine, [row]) == 1
    assert db.upsert_orders(engine, [row]) == 0  # дубль не вставлен
    loaded = db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert len(loaded) == 1
    assert loaded[0]["finished_price"] == 28070.60


def test_upsert_sales_kopecks(engine):
    row = {"saleID": "sa1", "date": "2026-10-06", "srid": "s1",
           "supplierArticle": "MC12", "finishedPrice": 2954800, "isCancel": False}
    db.upsert_sales(engine, [row])
    loaded = db.load_sales(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert loaded[0]["finished_price"] == 29548.0


def test_fbs_upsert(engine):
    from wb_sync.wb_api import WBClient
    from wb_sync.app_config import AppConfig as _AC  # для normalize нужен client
    import os
    client = WBClient(_AC(database_path="wb_sync.db", work_dir="/tmp/_wb_probe",
                          api_token="tok"))
    row = {"rid": "r1", "nmId": 1, "price": 2954800,
           "createdAt": 1761500000000,
           "statuses": {"isCancel": False, "supplierStatus": "delivering"}}
    assert db.upsert_fbs_orders(engine, [row], client) == 1
    assert db.upsert_fbs_orders(engine, [row], client) == 0
    loaded = db.load_fbs_orders(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert loaded[0]["status"] == "Доставляется"
    assert loaded[0]["price"] == 29548.0


def test_date_filter(engine):
    db.upsert_orders(engine, [
        {"srid": "a", "date": "2026-10-05", "supplierArticle": "X"},
        {"srid": "b", "date": "2026-09-05", "supplierArticle": "X"},
    ])
    loaded = db.load_orders(engine, date(2026, 10, 1), date(2026, 10, 31))
    assert [r["srid"] for r in loaded] == ["a"]
