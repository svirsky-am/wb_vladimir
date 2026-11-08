"""Клиент WB API: statistics v1, marketplace v3 (FBS), content v2 (карточки).

Все сырые ответы сохраняются в work_dir/responses/<имя>_<timestamp>.json.
Кеши выгрузок лежат в work_dir (управляется AppConfig.fetch_data).
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


class CachedDataMissingError(RuntimeError):
    """fetch_data=False, но кеш за период в work_dir отсутствует."""


def chunk_periods(start: date, end: date, size_days: int = 30):
    """Разбивает период на куски по size_days (WB v1: максимум 30 дней на запрос)."""
    chunks = []
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=size_days - 1), end)
        chunks.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return chunks


class WBClient:
    def __init__(self, config, session=None):
        self.config = config
        sbx = "-sandbox" if getattr(config, "sandbox", False) else ""
        self.common_base = f"https://common-api{sbx}.wildberries.ru"
        self.stat_base = f"https://statistics-api{sbx}.wildberries.ru"
        self.market_base = f"https://marketplace-api{sbx}.wildberries.ru"
        self.content_base = f"https://content-api{sbx}.wildberries.ru"
        self.session = session or requests.Session()
        self.session.headers.update({
            "Authorization": config.api_token,
            "Accept": "application/json",
        })

    # ---------- сохранение сырых ответов ----------
    def save_response(self, name: str, data) -> Path:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        path = self.config.responses_dir / f"{name}_{ts}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    # ---------- HTTP с ретраями на 429 ----------
    def _get(self, url: str, params=None):
        for attempt in range(3):
            r = self.session.get(url, params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            self.save_response("api_" + url.split("//")[-1].replace("/", "_"), data)
            return data
        r.raise_for_status()

    def _post(self, url: str, payload: dict):
        for attempt in range(3):
            r = self.session.post(url, json=payload, timeout=60)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            self.save_response("api_" + url.split("//")[-1].replace("/", "_"), data)
            return data
        r.raise_for_status()

    # ---------- кеш ----------
    def _cached_or_fetch(self, cache_name: str, fetcher):
        cache = self.config.work_dir / f"wb_{cache_name}.json"
        if not self.config.fetch_data:
            if not cache.exists():
                raise CachedDataMissingError(
                    f"fetch_data=False, но кеш отсутствует: {cache.name}. Сначала выполните выгрузку (fetch_data=True)."
                )
            return json.loads(cache.read_text(encoding="utf-8"))
        data = fetcher()
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def _cached_period(self, cache_name: str, start: date, end: date, fetcher):
        cache = self.config.work_dir / f"wb_{cache_name}_{start:%Y-%m-%d}_{end:%Y-%m-%d}.json"
        if not self.config.fetch_data:
            if not cache.exists():
                raise CachedDataMissingError(
                    f"fetch_data=False, но кеш отсутствует: {cache.name}. Сначала выполните выгрузку (fetch_data=True)."
                )
            return json.loads(cache.read_text(encoding="utf-8"))
        data = fetcher()
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # ---------- statistics-api v1: заказы и продажи ----------
    def _fetch_v1(self, url: str, start: date, end: date):
        rows = []
        for (a, b) in chunk_periods(start, end):
            params = {"dateFrom": f"{a:%Y-%m-%d}", "dateTo": f"{b:%Y-%m-%d}", "limit": 100000}
            page = self._get(url, params=params)
            if isinstance(page, list):
                rows.extend(page)
            else:
                rows.extend(page.get("data", []))
        return rows

    def get_orders(self, start: date, end: date):
        return self._cached_period("orders", start, end,
                                   lambda: self._fetch_v1(self.stat_base + "/api/v1/supplier/orders", start, end))

    def get_sales(self, start: date, end: date):
        return self._cached_period("sales", start, end,
                                   lambda: self._fetch_v1(self.stat_base + "/api/v1/supplier/sales", start, end))

    def get_stocks(self):
        return self._cached_or_fetch("stocks",
                                     lambda: self._get(self.stat_base + "/api/v1/supplier/stocks", params={"dateFrom": ""}))

    def get_incomes(self):
        return self._cached_or_fetch("incomes",
                                     lambda: self._get(self.stat_base + "/api/v1/supplier/incomes"))

    # ---------- marketplace-api v3: заказы FBS с честными статусами ----------
    STATUS_MAP = {
        "awaiting_packaging": "Ожидает сборки",
        "awaiting_deliver": "Готов к отгрузке",
        "delivering": "Доставляется",
        "sold": "Доставлен",
        "returned_to_seller": "Возврат",
        "declined_by_client": "Отменен",
        "broken": "Брак",
    }

    def normalize_status(self, row: dict) -> str:
        statuses = row.get("statuses") or {}
        if statuses.get("isCancel"):
            return "Отменен"
        return self.STATUS_MAP.get(statuses.get("supplierStatus") or "", "Неизвестен")

    def get_fbs_orders(self, start: date, end: date):
        def fetch():
            rows, nxt = [], 0
            while True:
                payload = {
                    "dateFrom": f"{start:%Y-%m-%d}T00:00:00",
                    "dateTo": f"{end:%Y-%m-%d}T23:59:59",
                    "limit": 1000,
                    "next": nxt,
                }
                data = self._post(self.market_base + "/api/v3/orders", payload)
                rows.extend(data.get("orders", []))
                nxt = data.get("next") or 0
                if not nxt:
                    break
            return rows
        return self._cached_period("fbs_orders", start, end, fetch)

    # ---------- content-api v2: карточки ----------
    def get_cards(self):
        """POST /content/v2/get/cards/list — пагинация курсором, максимум 100 карточек на запрос.

        Повторяем, пока total >= limit; последняя страница — когда total < limit.
        """

        def fetch():
            cards, cursor = [], {"limit": 100}
            while True:
                payload = {"settings": {
                    "filter": {"withPhoto": -1},
                    "sort": {"ascending": True},
                    "cursor": dict(cursor),
                }}
                data = self._post(self.content_base + "/content/v2/get/cards/list", payload)
                page = data.get("cards") or data.get("data", {}).get("cards") or []
                cur = data.get("cursor") or data.get("data", {}).get("cursor") or {}
                cards.extend(page)
                if not page or (cur.get("total") or 0) < 100:
                    break
                cursor = {"limit": 100, "updatedAt": cur["updatedAt"], "nmID": cur["nmID"]}
            return cards

        return self._cached_or_fetch("cards", fetch)

    def update_cards(self, payload: dict) -> dict:
        """POST /content/v2/cards/update — редактирование существующих карточек."""
        data = self._post(self.content_base + "/content/v2/cards/update", payload)
        return data

    def create_cards(self, payload: dict) -> dict:
        """POST /content/v2/cards/upload — создание новых карточек (в т.ч. дубликатов)."""
        data = self._post(self.content_base + "/content/v2/cards/upload", payload)
        return data
