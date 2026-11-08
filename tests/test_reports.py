from openpyxl import load_workbook

from wb_sync.reports import build_registry_rows, write_registry_xlsx


def _orders():
    return [
        {"srid": "s1", "date": "2026-10-05", "article": "MC12", "goods_name": "Пылесос",
         "warehouse": "Владимир", "office": "ИП Олейник", "finished_price": 29548.0, "is_cancel": False},
        {"srid": "s2", "date": "2026-10-06", "article": "MC12", "goods_name": "Пылесос",
         "warehouse": "Владимир", "office": "ИП Олейник", "finished_price": 26185.0, "is_cancel": True},
    ]


def _fbs():
    return {"s1": {"status": "Доставляется"}}


def test_registry_rows_use_fbs_status():
    rows = build_registry_rows(_orders(), _fbs())
    assert rows[0]["Статус"] == "Доставляется"      # из v3
    assert rows[1]["Статус"] == "Отменен"            # эвристика по is_cancel


def test_registry_rows_fallback():
    rows = build_registry_rows(_orders(), None)
    assert rows[0]["Статус"] == "Готов к отгрузке"


def test_xlsx_structure(tmp_path):
    sales = [
        {"date": "2026-10-05", "article": "MC12", "finished_price": 29548.0, "is_cancel": False, "goods_name": "Пылесос"},
        {"date": "2026-10-06", "article": "MC12", "finished_price": 26185.0, "is_cancel": True, "goods_name": "Пылесос"},
    ]
    path = write_registry_xlsx(build_registry_rows(_orders(), _fbs()),
                               tmp_path / "out.xlsx", sales=sales)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Реестр", "По дням", "По артикулам"]
    ws = wb["Реестр"]
    assert ws["A1"].value == "Магазин"
    assert ws["C2"].value == "Доставляется"
    assert ws["F2"].value == 29548.0
    assert wb["По дням"].max_row == 3
    assert wb["По артикулам"]["D2"].value == 55733.0


def test_empty_rows(tmp_path):
    path = write_registry_xlsx([], tmp_path / "empty.xlsx", sales=[])
    wb = load_workbook(path)
    assert wb["Реестр"].max_row == 1
