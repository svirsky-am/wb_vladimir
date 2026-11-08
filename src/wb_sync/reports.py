"""Генерация xlsx: реестр отгрузок в формате «М43 !ТУ Отгрузки FBS»."""

import logging
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

logger = logging.getLogger("wb_sync.reports")

HEADERS = ["Магазин", "Номер отправления", "Статус", "Принят",
           "Количество, артикул  Название товара", "Стоимость", "Склад"]

HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
HEADER_FONT = Font(bold=True)


def _fmt_row(order: dict, shop_name: str) -> list:
    created = order.get("date", "")
    if created and "T" in created:
        try:
            created = datetime.fromisoformat(created).strftime("%d.%m.%Y")
        except ValueError:
            pass
    qty = order.get("quantity", 1)
    label = f"{qty} шт, {order.get('article', '')}    {order.get('article_name', '')}"
    return [
        shop_name,
        order.get("srid", ""),
        order.get("status", ""),
        created,
        label,
        round(order.get("price", 0.0), 2),
        order.get("warehouseName", ""),
    ]


def build_registry_xlsx(orders, sales, fbs, out_path, shop_name: str = ""):
    """Собирает xlsx: лист «Реестр» + сводные «По дням» и «По артикулам».

    fbs: dict rid -> запись v3 (для статусов). Статус берётся из v3, если
    запись найдена, иначе fallback по isCancel заказа v1.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    rows = [_fmt_row(o, shop_name) for o in orders]
    if rows:
        ws.append(rows)
    for col, width in zip("ABCDEFG", (18, 24, 18, 12, 64, 12, 22)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2, min_col=6, max_col=6):
        for c in row:
            c.number_format = "# ##0.00"

    # сводный лист по дням
    by_day = {}
    for o in orders:
        day = (o.get("date") or "")[:10]
        if not day:
            continue
        price = o.get("price", 0.0)
        agg = by_day.setdefault(day, {"count": 0, "sum": 0.0, "cancel": 0})
        agg["count"] += o.get("quantity", 1)
        agg["sum"] += price * o.get("quantity", 1)
        if o.get("isCancel"):
            agg["cancel"] += 1
    ws2 = wb.create_sheet("По дням")
    ws2.append(["Дата", "Штук", "Выручка", "Отмены"])
    for cell in ws2[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for day in sorted(by_day):
        a = by_day[day]
        ws2.append([day, a["count"], round(a["sum"], 2), a["cancel"]])
    for col, width in zip("ABCD", (12, 10, 14, 10)):
        ws2.column_dimensions[col].width = width

    # сводный лист по артикулам
    by_art = {}
    for o in orders:
        art = o.get("article", "") or "<без артикула>"
        qty = o.get("quantity", 1)
        agg = by_art.setdefault(art, {"count": 0, "sum": 0.0, "cancel": 0, "name": o.get("article_name", "")})
        agg["count"] += qty
        agg["sum"] += o.get("price", 0.0) * qty
        if o.get("isCancel"):
            agg["cancel"] += 1
    ws3 = wb.create_sheet("По артикулам")
    ws3.append(["Артикул", "Название", "Штук", "Выручка", "Средняя цена", "Отмены"])
    for cell in ws3[1]:
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for art in sorted(by_art):
        a = by_art[art]
        avg = a["sum"] / a["count"] if a["count"] else 0.0
        ws3.append([art, a["name"], a["count"], round(a["sum"], 2), round(avg, 2), a["cancel"]])
    for col, width in zip("ABCDEF", (22, 44, 8, 14, 14, 8)):
        ws3.column_dimensions[col].width = width

    wb.save(out_path)
    logger.info("Отчёт сохранён: %s (строк: %d)", out_path, len(rows))
    return out_path
