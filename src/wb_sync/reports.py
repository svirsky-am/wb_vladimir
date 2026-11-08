"""Генерация xlsx: Реестр + сводные листы."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter


def build_registry_rows(orders, fbs_by_srid):
    rows = []
    for o in orders:
        srid = str(o.get("srid") or "")
        fbs = fbs_by_srid.get(srid)
        if fbs and fbs.get("status"):
            status = fbs["status"]
        else:
            status = "Отменен" if o.get("isCancel") else "Готов к отгрузке"
        rows.append({
            "Магазин": "WB",
            "Номер отправления": srid,
            "Статус": status,
            "Принят": (o.get("date") or "")[:10],
            "Кол-во, артикул": f"1 шт, {o.get('supplierArticle') or ''}",
            "Название товара": o.get("subjectName") or "",
            "Стоимость": o.get("finishedPrice") or 0.0,
            "Склад": o.get("warehouseName") or "",
        })
    rows.sort(key=lambda r: r["Принят"], reverse=True)
    return rows


def build_registry_xlsx(rows, date_from: date, date_to: date, out_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр"
    headers = ["Магазин", "Номер отправления", "Статус", "Принят", "Кол-во, артикул",
               "Название товара", "Стоимость", "Склад"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDDDDD")
    for r in rows:
        ws.append([r[h] for h in headers])
    for i, w in enumerate([14, 24, 18, 12, 40, 60, 12, 22], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    by_day = defaultdict(lambda: {"cnt": 0, "sum": 0.0, "cancel": 0})
    by_art = defaultdict(lambda: {"cnt": 0, "sum": 0.0, "cancel": 0})
    for r in rows:
        key_day = r["Принят"]
        key_art = r["Кол-во, артикул"].split(", ", 1)[-1]
        v = r["Стоимость"] or 0.0
        for agg, key in ((by_day, key_day), (by_art, key_art)):
            agg[key]["cnt"] += 1
            agg[key]["sum"] += 0 if r["Статус"] == "Отменен" else v
            if r["Статус"] == "Отменен":
                agg[key]["cancel"] += 1

    def summary_sheet(title, agg, key_name):
        s = wb.create_sheet(title)
        s.append([key_name, "Позиций", "Отменено", "Выручка, ₽"])
        for c in s[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDDDDD")
        for key, v in sorted(agg.items(), key=lambda kv: str(kv[0]), reverse=True):
            s.append([key, v["cnt"], v["cancel"], round(v["sum"], 2)])
        for i, w in enumerate([30, 10, 10, 14], start=1):
            s.column_dimensions[get_column_letter(i)].width = w

    summary_sheet("По дням", by_day, "Дата")
    summary_sheet("По артикулам", by_art, "Артикул")
    wb.save(out_path)
    return out_path
