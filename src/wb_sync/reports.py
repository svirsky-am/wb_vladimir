"""XLSX-реестр: листы Реестр / По дням / По артикулам."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEAD_FILL = PatternFill("solid", fgColor="D9E1F2")
HEAD_FONT = Font(bold=True)


def _autowidth(ws) -> None:
    for col in range(1, ws.max_column + 1):
        width = max((len(str(ws.cell(r, c).value or "")) for r in range(1, ws.max_row + 1) for c in [col]), default=10)
        ws.column_dimensions[get_column_letter(col)].width = min(width + 2, 80)


def build_xlsx(registry: list[dict], by_day: dict, by_article: dict, out_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр"
    headers = ["Магазин", "Номер отправления", "Статус", "Принят", "Артикул", "Название товара", "Стоимость", "Склад"]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        ws.cell(1, c).fill = HEAD_FILL
        ws.cell(1, c).font = HEAD_FONT
    for r in registry:
        ws.append([r.get(h) for h in headers])
    _autowidth(ws)

    ws2 = wb.create_sheet("По дням")
    ws2.append(["Дата", "Выручка"])
    ws2["A1"].font = HEAD_FONT
    ws2["B1"].font = HEAD_FONT
    for d in sorted(by_day):
        ws2.append([d, round(by_day[d], 2)])
    _autowidth(ws2)

    ws3 = wb.create_sheet("По артикулам")
    ws3.append(["Артикул", "Штук", "Выручка", "Средняя цена"])
    for c in range(1, 5):
        ws3.cell(1, c).font = HEAD_FONT
    for art, agg in sorted(by_article.items()):
        avg = round(agg["revenue"] / agg["count"], 2) if agg["count"] else 0
        ws3.append([art, agg["count"], round(agg["revenue"], 2), avg])
    _autowidth(ws3)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path
