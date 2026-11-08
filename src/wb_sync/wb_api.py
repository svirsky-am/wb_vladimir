"""Клиент API Wildberries: логирование, троттлинг, ретраи, кеш, песочница."""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .app_config import AppConfig

logger = logging.getLogger(__name__)

STATUS_RU = {
    "new": "Ожидает сборки",
    "confirm": "Готов к отгрузке",
    "complete": "Доставляется",
    "delivered": "Доставлен",
    "cancel": "Отменен",
    "cancellation": "Отменен",
    "delivering": "Доставляется",
}


class CachedDataMissingError(RuntimeError):
    """Данных нет ни в сети (fetch_data=False), ни в кеше."""


def normalize_v3_status(status: str) -> str:
    return STATUS_RU.get((status or "").lower(), status or "неизвестно")


def status_to_ru(client: "WBClient", status: str, is_cancel: bool) -> str:
    ru = normalize_v3_status(status)
    if is_cancel and ru != "Отменен":
        ru = "Отменен"
    return ru


def chunk_periods(date_from: date, date_to: date, window_days: int = 30):
    """Период -> чанки по window_days включительно (лимит WB — 30 дней на запрос)."""
    if date_to < date_from:
        raise ValueError("date_to раньше date_from")
    chunks = []
    cur = date_from
    while cur <= date_to:
        end = min(cur + timedelta(days=window_days - 1), date_to)
        chunks.append((cur, end))
        cur = end + timedelta(days=1)
    return chunks


def _ms(dt: date) -> int:
    return int(datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).timestamp() * 1000)


class WBClient:
    V1_HOST = "https://statistics-api.wildberries.ru"
    V3_HOST = "https://marketplace-api.wildberries.ru"
    CONTENT_HOST = "https://content-api.wildberries.ru"
    COMMON_HOST = "https://common-api.wildberries.ru"

    def __init__(self, config: AppConfig):
        self.config = config
        self._session = threading.local()
        self._last_request_at = 0.0
        self._throttle_lock = threading.Lock()

    # --- песочница -------------------------------------------------------
    def _host(self, base: str) -> str:
        if not self.config.sandbox:
            return base
        # statistics-api.wildberries.ru -> statistics-api-sandbox.wildberries.ru
        return base.replace(".wildberries.ru", "-sandbox.wildberries.ru")

    # --- сессия и троттлинг ----------------------------------------------
    @property
    def session(self) -> requests.Session:
        # разрешаем переходить у тестов через singledispatch/patch.object
        s = getattr(self._session, "s", None)
        if s is None:
            s = requests.Session()
            s.headers.update({"Authorization": self.config.api_token, "Accept": "application/json"})
            self._session.s = s
        return s

    @session.setter
    def session(self, value: requests.Session) -> None:
        self._session.s = value

    @session.deleter
    def session(self) -> None:
        self._session.s = None

    def _throttle(self) -> None:
        interval = max(self.config.min_request_interval, 0.0)
        while True:
            with self._throttle_lock:
                now = time.monotonic()
                wait = self._last_request_at + interval - now
                if wait <= 0:
                    self._last_request_at = now
                    return
            time.sleep(min(wait, 0.5))

    def _save_response(self, label: str, payload) -> None:
        """Сырой ответ -> work_dir/responses/<label>_<timestamp>.json"""
        try:
            d = self.config.work_dir / "responses"
            d.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            path = d / f"{label}_{ts}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        except Exception:  # сохранение ответа не должно ломать выгрузку
            logger.warning("Не удалось сохранить сырой ответ %s", label, exc_info=True)

    # --- ядро запроса -----------------------------------------------------
    def request(self, method: str, url: str, label: str = "", *, params=None, json_body=None) -> object:
        label = label or f"{method} {url}"
        total = self.config.max_retries + 1
        last_err = None
        for attempt in range(1, total + 1):
            self._throttle()
            started = time.monotonic()
            try:
                logger.info("Попытка %d/%d %s", attempt, total, label)
                resp = self.session.request(method, url, params=params, json=json_body, timeout=60)
                elapsed = time.monotonic() - started
                if resp.status_code == 200:
                    logger.info("%s → 200 (%.1f КБ, %.2f с)", label, len(resp.content) / 1024, elapsed)
                    return resp.json()
                if resp.status_code == 429 or resp.status_code >= 500:
                    logger.info("Попытка %d/%d %s — HTTP %d (%.2f с)", attempt, total, label, resp.status_code, elapsed)
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if (retry_after or "").isdigit() else self.config.retry_base_delay * (2 ** (attempt - 1))
                    logger.info("HTTP %d: пауза %.0f с перед попыткой %d/%d", resp.status_code, delay, attempt + 1, total)
                    last_err = f"HTTP {resp.status_code}"
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
            except requests.HTTPError:
                logger.error("Запрос не удался окончательно: %s — HTTP %d", label, resp.status_code)
                raise
            except requests.RequestException as exc:
                logger.info("Попытка %d/%d %s — сетевая ошибка: %s", attempt, total, label, exc)
                last_err = str(exc)
                delay = self.config.retry_base_delay * (2 ** (attempt - 1))
                time.sleep(delay)
        logger.error("Запрос не удался окончательно: %s", label)
        raise RuntimeError(f"Запрос не удался после {total} попыток: {label} — {last_err}")

    # --- ping -------------------------------------------------------------
    def ping(self) -> dict:
        return self.request("GET", f"{self._host(self.COMMON_HOST)}/ping", label="GET /ping")

    # --- statistics-api v1 --------------------------------------------------
    def _fetch_v1(self, path: str, label: str, date_from: date, date_to: date) -> list:
        """v1: если fetch_data — сеть (обновляя кеш), иначе — только кеш всего периода."""
        key = f"v1_{path.rsplit('/', 1)[-1]}_{date_from}_{date_to}"
        cache = self.config.work_dir / f"{key}.json"
        if not self.config.fetch_data:
            if cache.exists():
                logger.info("Кеш: %s", cache.name)
                return json.loads(cache.read_text(encoding="utf-8"))
            raise CachedDataMissingError(
                f"Кеш {cache.name} не найден, а fetch_data=False — запустите sync с выгрузкой")
        rows = []
        for a, b in chunk_periods(date_from, date_to, self.config.fetch_window_days):
            data = self.request("GET", f"{self._host(self.V1_HOST)}{path}", label=f"GET {path} {a}..{b}",
                                params={"dateFrom": a.isoformat(), "dateTo": b.isoformat(), "limit": 100000})
            rows.extend(data if isinstance(data, list) else [])
        cache.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return rows

    def get_orders(self, date_from: date, date_to: date) -> list:
        return self._fetch_v1("/api/v1/supplier/orders", "orders", date_from, date_to)

    def get_sales(self, date_from: date, date_to: date) -> list:
        return self._fetch_v1("/api/v1/supplier/sales", "sales", date_from, date_to)

    def get_incomes(self, date_from: date, date_to: date) -> list:
        return self._fetch_v1("/api/v1/supplier/incomes", "incomes", date_from, date_to)

    def get_stocks(self) -> list:
        if not self.config.fetch_data:
            return self._read_cache("v1_stocks", [])
        data = self.request("GET", f"{self._host(self.V1_HOST)}/api/v1/supplier/stocks", label="GET /api/v1/supplier/stocks")
        self._write_cache("v1_stocks", data)
        return data

    def get_warehouses(self) -> list:
        if not self.config.fetch_data:
            return self._read_cache("v1_warehouses", [])
        data = self.request("GET", f"{self._host(self.V1_HOST)}/api/v1/supplier/warehouses", label="GET /api/v1/supplier/warehouses")
        self._write_cache("v1_warehouses", data)
        return data

    def _cache_path(self, key: str) -> Path:
        return self.config.work_dir / f"{key}.json"

    def _write_cache(self, key: str, data) -> None:
        self._cache_path(key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _read_cache(self, key: str, default):
        p = self._cache_path(key)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return default

    # --- marketplace-api v3 -------------------------------------------------
    def get_v3_orders(self, date_from: date, date_to: date) -> list:
        """GET /api/v3/orders: limit<=1000, next, dateFrom/dateTo в Unix-секундах, окно <= 30 дней."""
        rows = []
        for a, b in chunk_periods(date_from, date_to, self.config.fetch_window_days):
            next_cursor = 0
            while True:
                data = self.request(
                    "GET", f"{self._host(self.V3_HOST)}/api/v3/orders",
                    label=f"GET /api/v3/orders {a}..{b} next={next_cursor}",
                    params={"dateFrom": int(datetime(a.year, a.month, a.day, tzinfo=timezone.utc).timestamp()),
                            "dateTo": int(datetime(b.year, b.month, b.day, 23, 59, 59, tzinfo=timezone.utc).timestamp()),
                            "limit": 1000, "next": next_cursor})
                rows.extend(data.get("orders", []))
                next_cursor = data.get("next", 0)
                if not next_cursor:
                    break
        self._write_cache(f"v3_orders_{date_from}_{date_to}", rows)
        return rows

    # --- content-api: карточки ----------------------------------------------
    def get_cards(self) -> list:
        """POST /content/v2/get/cards/list — курсорная пагинация (limit<=100)."""
        host = self._host(self.CONTENT_HOST)
        cards, cursor = [], {"limit": 100}
        while True:
            data = self.request("POST", f"{host}/content/v2/get/cards/list", label="POST /content/v2/get/cards/list",
                                json_body={"settings": {"cursor": cursor, "filter": {"withPhotoOnly": False}}})
            body = data.get("data", {})
            cards.extend(body.get("cards", []))
            total = body.get("total", 0)
            new_cursor = body.get("cursor")
            if total < cursor["limit"] or not new_cursor:
                break
            cursor = new_cursor
        self._write_cache("cards", cards)
        return cards

    def update_cards(self, payload: dict) -> object:
        return self.request("POST", f"{self._host(self.CONTENT_HOST)}/content/v2/cards/update",
                            label="POST /content/v2/cards/update", json_body=payload)

    def create_cards(self, payload: dict) -> object:
        return self.request("POST", f"{self._host(self.CONTENT_HOST)}/content/v2/cards/upload",
                            label="POST /content/v2/cards/upload", json_body=payload)

    # --- параллельная выгрузка ----------------------------------------------
    def fetch_parallel(self, tasks: dict) -> dict:
        """tasks: {имя: callable}. Возвращает {имя: результат или None}. Ошибка задачи не роняет остальные."""
        results = {}

        def run(name, fn):
            try:
                return name, fn()
            except Exception:
                logger.exception("Задача %s упала", name)
                return name, None

        with ThreadPoolExecutor(max_workers=max(self.config.fetch_workers, 1)) as pool:
            futures = [pool.submit(run, name, fn) for name, fn in tasks.items()]
            for fut in futures:
                name, value = fut.result()
                results[name] = value
        return results
