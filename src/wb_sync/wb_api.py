"""Клиент WB API с кешированием в work_dir.

- statistics-api: supplier/orders, supplier/sales (v1, чанки по 30 дней)
- marketplace-api: /api/v3/orders (POST, пагинация через next)
"""

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

STATISTICS_BASE = "https://statistics-api.wildberries.ru"
MARKETPLACE_BASE = "https://marketplace-api.wildberries.ru"
PING_URL = "https://common-api.wildberries.ru/ping"

RETRY_STATUSES = {429, 500, 502, 503}
MAX_RETRIES = 5
RETRY_BACKOFF = 5  # секунд, растёт линейно


class CachedDataMissingError(RuntimeError):
    pass


def _iso(d: date) -> str:
    return d.isoformat()


def chunk_periods(date_from: date, date_to: date, max_days: int = 30):
    current = date_from
    while current <= date_to:
        chunk_end = min(current + timedelta(days=max_days - 1), date_to)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


class WBClient:
    def __init__(self, app_config):
        self.cfg = app_config
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": app_config.api_token, "Accept": "application/json"}
        )

    # ---------- низкий уровень ----------
    def _request(self, method: str, url: str, **kwargs):
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            resp = self.session.request(method, url, timeout=60, **kwargs)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * attempt
                time.sleep(wait)
                last_error = RuntimeError(
                    f"{method} {url} -> {resp.status_code}, попытка {attempt}"
                )
                continue
            raise RuntimeError(
                f"{method} {url} -> {resp.status_code}: {resp.text[:300]}"
            )
        raise last_error

    def _cache_path(self, name: str, date_from: date, date_to: date) -> Path:
        return self.cfg.work_dir / f"wb_{name}_{_iso(date_from)}_{_iso(date_to)}.json"

    def _save_cache(self, name: str, date_from: date, date_to: date, data) -> Path:
        path = self._cache_path(name, date_from, date_to)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def _load_cache(self, name: str, date_from: date, date_to: date):
        path = self._cache_path(name, date_from, date_to)
        if not path.exists():
            raise CachedDataMissingError(
                f"Кеш {path.name} не найден. Запустите sync с fetch_data=True."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    # ---------- v1 statistics-api ----------
    def _fetch_v1(self, name: str, path: str, date_from: date, date_to: date, limit: int = 100000):
        all_rows = []
        for chunk_from, chunk_to in chunk_periods(date_from, date_to):
            rows = self._request(
                "GET",
                f"{STATISTICS_BASE}{path}",
                params={
                    "dateFrom": _iso(chunk_from),
                    "dateTo": _iso(chunk_to),
                    "rrdid": 0,
                    "limit": limit,
                },
            )
            all_rows.extend(rows)
            self._save_cache(f"{name}_{_iso(chunk_from)}_{_iso(chunk_to)}", chunk_from, chunk_to, rows)
        return all_rows

    def get_orders(self, date_from: date, date_to: date):
        return self._fetch_v1("orders", "/api/v1/supplier/orders", date_from, date_to)

    def get_sales(self, date_from: date, date_to: date):
        return self._fetch_v1("sales", "/api/v1/supplier/sales", date_from, date_to)

    # ---------- v3 marketplace-api ----------
    def get_fbs_orders(self, date_from: date, date_to: date):
        """POST /api/v3/orders — пагинация через next, лимит 1000."""
        all_rows = []
        cursor = 0
        while True:
            payload = {
                "filter": {
                    "dateFrom": int(datetime(date_from.year, date_from.month, date_from.day).timestamp()),
                    "dateTo": int(datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59).timestamp()),
                },
                "limit": 1000,
                "next": cursor,
                "order": "asc",
            }
            resp = self._request(
                "POST", f"{MARKETPLACE_BASE}/api/v3/orders", json=payload
            )
            rows = resp.get("orders", [])
            all_rows.extend(rows)
            nxt = resp.get("next")
            if not nxt or not rows:
                break
            cursor = nxt
        self._save_cache("fbs_orders", date_from, date_to, all_rows)
        return all_rows

    # ---------- кеш-режим ----------
    def load_orders(self, date_from, date_to):
        return self._gather_cache("orders", date_from, date_to)

    def load_sales(self, date_from, date_to):
        return self._gather_cache("sales", date_from, date_to)

    def load_fbs_orders(self, date_from, date_to):
        return self._gather_cache("fbs_orders", date_from, date_to)

    def _gather_cache(self, name: str, date_from: date, date_to: date):
        rows = []
        for chunk_from, chunk_to in chunk_periods(date_from, date_to):
            rows.extend(self._load_cache(f"{name}_{_iso(chunk_from)}_{_iso(chunk_to)}", chunk_from, chunk_to))
        return rows

    # ---------- прочее ----------
    def ping(self) -> dict:
        return self._request("GET", PING_URL, params={})

    # ---------- нормализация ----------
    _STATUS_MAP = {
        "new_order": "Готов к отгрузке",
        "awaiting_packaging": "Готов к отгрузке",
        "sorted_to_ship": "Готов к отгрузке",
        "canceled": "Отменен",
        "delivering": "Доставляется",
        "delivered": "Доставлен",
        "declined_by_supplier": "Отменен",
    }

    def normalize_fbs_status(self, order: dict) -> str:
        statuses = order.get("statuses") or {}
        if statuses.get("isCancel"):
            return "Отменен"
        supplier = statuses.get("supplierStatus") or ""
        wb = statuses.get("wbStatus") or ""
        return self._STATUS_MAP.get(supplier or wb, "В обработке")

    @staticmethod
    def rub_from_kopecks(value) -> float:
        return round((value or 0) / 100, 2)
