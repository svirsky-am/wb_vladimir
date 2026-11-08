"""Генерация xlsx-реестра в формате «Реестр Озон/ВБ» + сводные листы.

Функции принимают готовые строки (list[dict]) — их можно собрать из БД
или из тестовых моков, sqlalchemy здесь не нужен.
"""

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER = [
    "Магазин", "Номер отправления", "Статус", "Принят",
    "Кол-во, артикул  Название товара", "Стоимость", "Склад",
]

_MONEY_FMT = "#,##0.00 ₽"


def _parse_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y")
    except ValueError:
        return value


def build_registry_rows(orders: list[dict], fbs_by_srid: dict[str, dict] | None = None) -> list[dict]:
    fbs_by_srid = fbs_by_srid or {}
    rows = []
    for o in orders:
        srid = str(o.get("srid", ""))
        fbs = fbs_by_srid.get(srid)
        if fbs:
            status = fbs.get("status") or ""
        else:
            status = "Отменен" if o.get("is_cancel") else "Готов к отгрузке"
        article = o.get("article") or ""
        name = o.get("goods_name") or ""
        rows.append(
            {
                "Магазин": o.get("office") or "ИП",
                "Номер отправления": srid,
                "Статус": status,
                "Принят": _parse_date(o.get("date")),
                "Кол-во, артикул  Название товара": f"1 шт, {article}    {name}",
                "Стоимость": o.get("finished_price") or 0.0,
                "Склад": o.get("warehouse") or "",
            }
        )
    return rows


def _autowidth(ws, min_width: int = 10, max_width: int = 60):
    for idx, cell in enumerate(ws[1], start=1):
        col_values = [str(ws.cell(row=r, column=idx).value or "") for r in range(1, ws.max_row + 1)]
        width = max(min(len(v) for v in col_values) * 1.0, min_width)
        ws.column_dimensions[get_column_letter(idx)].width = min(
            max(width, max(len(str(cell.value or "")) + 2, min_width)), max_width
        )


def write_registry_xlsx(
    rows: list[dict],
    out_path: str | Path,
    sales: list[dict] | None = None,
) -> Path:
    wb = Workbook()

    # Лист «Реестр»
    ws = wb.active
    ws.title = "Реестр"
    ws.append(HEADER)
    header_fill = PatternFill("solid", fgColor="DDEBF7")
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    for row in rows:
        ws.append([row.get(col, "") for col in HEADER])
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=6).number_format = _MONEY_FMT
    _autowidth(ws)

    # Лист «По дням»
    if sales:
        daily = {}
        for s in sales:
            key = s.get("date") or ""
            agg = daily.setdefault(key, {"count": 0, "revenue": 0.0, "cancels": 0})
            agg["count"] += 1
            agg["revenue"] += s.get("finished_price") or 0.0
            agg["cancels"] += int(bool(s.get("is_cancel")))
        ws2 = wb.create_sheet("По дням")
        ws2.append(["Дата", "Выкуплено позиций", "Выручка", "Отмены"])
        for cell in ws2[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        for key in sorted(daily):
            d = daily[key]
            ws2.append([_parse_date(key), d["count"], d["revenue"], d["cancels"]])
        for r in range(2, ws2.max_row + 1):
            ws2.cell(row=r, column=3).number_format = _MONEY_FMT
        _autowidth(ws2)

        # Лист «По артикулам»
        arts = {}
        for s in sales:
            key = s.get("article") or ""
            agg = arts.setdefault(key, {"count": 0, "revenue": 0.0, "cancels": 0, "name": s.get("goods_name") or ""})
            agg["count"] += 1
            agg["revenue"] += s.get("finished_price") or 0.0
            agg["cancels"] += int(bool(s.get("is_cancel")))
        ws3 = wb.create_sheet("По артикулам")
        ws3.append(["Артикул", "Название товара", "Выкуплено позиций", "Выручка", "Средняя цена", "Отмены"])
        for cell in ws3[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        for key in sorted(arts):
            a = arts[key]
            avg = round(a["revenue"] / a["count"], 2) if a["count"] else 0.0
            ws3.append([key, a["name"], a["count"], a["revenue"], avg, a["cancels"]])
        for r in range(2, ws3.max_row + 1):
            ws3.cell(row=r, column=4).number_format = _MONEY_FMT
            ws3.cell(row=r, column=5).number_format = _MONEY_FMT
        _autowidth(ws3)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
